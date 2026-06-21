import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch


CURRENT_DIR = os.path.dirname(__file__)
BACKEND_DIR = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

import httpx

from app.bootstrap import build_company_os
from app.budget.guard import BudgetGuard
from app.core.models import BudgetPolicy
from app.knowledge_base.embeddings import (
    EMBEDDING_DIMENSIONS,
    EmbeddingGateway,
    EmbeddingProviderError,
    OpenAIEmbeddingProvider,
    ProviderEmbedding,
)
from app.models.gateway import ModelGateway, create_model_gateway
from app.models.providers import (
    ModelProviderConfigurationError,
    ModelProviderError,
    OpenAIResponsesProvider,
    ProviderGeneration,
)
from app.persistence.sqlite_store import SQLiteStateStore
from app.services.company import CompanyApplicationService


class _FakeModelProvider:
    name = "fake"
    default_model = "fake-model-v1"

    def generate(self, prompt, model_name, purpose, max_output_tokens):
        return ProviderGeneration(
            output=f"real output for {purpose}",
            prompt_tokens=11,
            completion_tokens=7,
            total_tokens=18,
        )


class _FailingModelProvider(_FakeModelProvider):
    def generate(self, prompt, model_name, purpose, max_output_tokens):
        raise ModelProviderError("fake model endpoint unavailable")


class _FakeEmbeddingProvider:
    name = "fake"
    default_model = "fake-embedding-v1"

    def embed(self, text, model_name):
        values = [0.0] * EMBEDDING_DIMENSIONS
        values[0] = 1.0
        return ProviderEmbedding(values=values, input_tokens=9)


class _FailingEmbeddingProvider(_FakeEmbeddingProvider):
    def embed(self, text, model_name):
        raise EmbeddingProviderError("fake embedding endpoint unavailable")


class _VectorSQLiteStore(SQLiteStateStore):
    def __init__(self, path):
        super().__init__(path)
        self.vectors = {}

    def list_knowledge_embedding_doc_ids(self):
        return set(self.vectors)

    def upsert_knowledge_embedding(self, doc_id, embedding, metadata=None):
        self.vectors[doc_id] = {"embedding": embedding, "metadata": metadata or {}}

    def search_knowledge_embeddings(self, embedding, *, limit=10):
        return [
            {"doc_id": doc_id, "score": 0.92, "metadata": record["metadata"]}
            for doc_id, record in list(self.vectors.items())[:limit]
        ]


class ModelProviderTests(unittest.TestCase):
    def test_openai_responses_provider_parses_text_and_usage(self):
        observed = {}

        def handler(request):
            observed["path"] = request.url.path
            observed["authorization"] = request.headers.get("authorization")
            observed["body"] = json.loads(request.content)
            return httpx.Response(
                200,
                request=request,
                json={
                    "output": [
                        {
                            "type": "message",
                            "content": [{"type": "output_text", "text": "Provider result"}],
                        }
                    ],
                    "usage": {"input_tokens": 12, "output_tokens": 4, "total_tokens": 16},
                },
            )

        client = httpx.Client(
            base_url="https://api.openai.com/v1",
            headers={"Authorization": "Bearer test-key"},
            transport=httpx.MockTransport(handler),
        )
        provider = OpenAIResponsesProvider(
            "test-key", default_model="test-model", client=client
        )

        result = provider.generate(
            "Sensitive prompt", "test-model", "unit_test", 321
        )

        self.assertEqual(observed["path"], "/v1/responses")
        self.assertEqual(observed["authorization"], "Bearer test-key")
        self.assertEqual(observed["body"]["model"], "test-model")
        self.assertFalse(observed["body"]["store"])
        self.assertEqual(observed["body"]["max_output_tokens"], 321)
        self.assertEqual(result.output, "Provider result")
        self.assertEqual(result.total_tokens, 16)

    def test_openai_responses_provider_sanitizes_http_errors(self):
        def handler(request):
            return httpx.Response(
                429,
                request=request,
                headers={"x-request-id": "req_test"},
                json={"error": {"message": "do not expose provider detail"}},
            )

        provider = OpenAIResponsesProvider(
            "test-key",
            default_model="test-model",
            client=httpx.Client(
                base_url="https://api.openai.com/v1",
                transport=httpx.MockTransport(handler),
            ),
        )

        with self.assertRaisesRegex(ModelProviderError, "HTTP 429.*req_test") as raised:
            provider.generate("prompt", "test-model", "unit_test", 100)
        self.assertNotIn("do not expose", str(raised.exception))

    def test_gateway_selects_provider_and_hashes_references(self):
        gateway = ModelGateway(
            providers={"fake": _FakeModelProvider()}, default_provider="fake"
        )

        response = gateway.generate(
            "Private model input",
            actor_id="document_agent_v1",
            purpose="provider_test",
        )

        self.assertEqual(response.output, "real output for provider_test")
        self.assertEqual(response.usage.provider, "fake")
        self.assertEqual(response.usage.model_name, "fake-model-v1")
        self.assertTrue(response.usage.input_ref.startswith("input_sha256_"))
        self.assertNotIn("Private model input", response.usage.input_ref)
        with self.assertRaisesRegex(ModelProviderConfigurationError, "not allowlisted"):
            gateway.generate(
                "Private model input",
                actor_id="document_agent_v1",
                purpose="provider_test",
                model_name="unapproved-model",
            )

    def test_budget_guard_caps_output_against_call_and_remaining_totals(self):
        guard = BudgetGuard(
            BudgetPolicy(
                max_tokens_per_call=100,
                max_total_tokens=120,
                max_estimated_cost=10,
                cost_per_token=0.001,
            )
        )
        guard.record_cost(
            source_type="model_usage",
            source_id="prior",
            actor_id="document_agent_v1",
            task_id=None,
            tokens=50,
            amount=0.05,
            result="recorded",
            reason="prior usage",
        )

        self.assertEqual(guard.max_output_tokens("x" * 40), 60)

    def test_model_factory_rejects_unconfigured_default_provider(self):
        with patch.dict(
            os.environ,
            {"AI_COMPANY_OS_MODEL_PROVIDER": "openai"},
            clear=True,
        ):
            with self.assertRaises(ModelProviderConfigurationError):
                create_model_gateway()
        with self.assertRaisesRegex(ModelProviderConfigurationError, "must use HTTPS"):
            OpenAIResponsesProvider(
                "test-key",
                default_model="test-model",
                base_url="http://models.example.test/v1",
            )

    def test_model_failure_creates_audit_cost_and_incident_records(self):
        model_gateway = ModelGateway(
            providers={"fake": _FailingModelProvider()}, default_provider="fake"
        )
        service = CompanyApplicationService(
            company_os=build_company_os(model_gateway=model_gateway)
        )

        with self.assertRaisesRegex(ModelProviderError, "endpoint unavailable"):
            service.generate_model_response(
                prompt="Provider failure test",
                actor_id="document_agent_v1",
                purpose="failure_test",
            )

        self.assertEqual(service.list_cost_logs()[-1]["result"], "failed")
        self.assertEqual(service.list_audit_logs()[-1]["event_type"], "model_failed")
        self.assertEqual(service.list_incidents()[-1]["source_type"], "model_usage")

    def test_openai_embedding_provider_requests_fixed_pgvector_dimensions(self):
        observed = {}

        def handler(request):
            observed["path"] = request.url.path
            observed["body"] = json.loads(request.content)
            return httpx.Response(
                200,
                request=request,
                json={
                    "data": [{"embedding": [0.25] * EMBEDDING_DIMENSIONS}],
                    "usage": {"prompt_tokens": 6, "total_tokens": 6},
                },
            )

        provider = OpenAIEmbeddingProvider(
            "test-key",
            client=httpx.Client(
                base_url="https://api.openai.com/v1",
                transport=httpx.MockTransport(handler),
            ),
        )
        result = provider.embed("Knowledge text", provider.default_model)

        self.assertEqual(observed["path"], "/v1/embeddings")
        self.assertEqual(observed["body"]["dimensions"], EMBEDDING_DIMENSIONS)
        self.assertEqual(observed["body"]["encoding_format"], "float")
        self.assertEqual(len(result.values), EMBEDDING_DIMENSIONS)
        self.assertEqual(result.input_tokens, 6)

    def test_openai_embedding_provider_rejects_wrong_dimensions(self):
        def handler(request):
            return httpx.Response(
                200,
                request=request,
                json={"data": [{"embedding": [0.25]}], "usage": {}},
            )

        provider = OpenAIEmbeddingProvider(
            "test-key",
            client=httpx.Client(
                base_url="https://api.openai.com/v1",
                transport=httpx.MockTransport(handler),
            ),
        )
        with self.assertRaisesRegex(EmbeddingProviderError, "1536"):
            provider.embed("Knowledge text", provider.default_model)


class KnowledgeEmbeddingIntegrationTests(unittest.TestCase):
    def _service(self, path, provider=None):
        gateway = EmbeddingGateway(
            providers={"fake": provider or _FakeEmbeddingProvider()},
            default_provider="fake",
        )
        store = _VectorSQLiteStore(path)
        service = CompanyApplicationService(
            company_os=build_company_os(), persistence=store, embeddings=gateway
        )
        return service, store

    def test_knowledge_write_indexes_and_semantic_search_is_audited(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            service, store = self._service(os.path.join(tmpdir, "vectors.db"))
            created = service.write_knowledge(
                "Operating policy", "Human Root approves high-risk external actions."
            )

            results = service.search_knowledge(
                "Who approves dangerous actions?", actor_id="memory_agent_v1"
            )

            self.assertIn(created["doc_id"], store.vectors)
            self.assertEqual(results[0]["doc_id"], created["doc_id"])
            self.assertEqual(len(service.list_model_usage()), 2)
            self.assertEqual(
                service.list_model_usage()[0]["purpose"], "knowledge_embedding"
            )
            self.assertEqual(
                service.list_model_usage()[1]["purpose"], "knowledge_query_embedding"
            )
            self.assertEqual(
                service.list_audit_logs()[-1]["event_type"],
                "knowledge_embedding_searched",
            )
            self.assertEqual(service.embedding_status()["indexed_documents"], 1)

    def test_embedding_failure_keeps_lexical_search_available(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            service, _ = self._service(
                os.path.join(tmpdir, "vectors.db"), _FailingEmbeddingProvider()
            )
            created = service.write_knowledge(
                "Fallback policy", "Lexical fallback stays available."
            )

            results = service.search_knowledge("Fallback policy")

            self.assertEqual(results[0]["doc_id"], created["doc_id"])
            self.assertEqual(service.embedding_status()["failed_documents"], 1)
            self.assertGreaterEqual(len(service.list_incidents()), 1)
            self.assertIn(
                "embedding_failed",
                [event["event_type"] for event in service.list_audit_logs()],
            )

    def test_only_human_root_can_force_reindex(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            service, _ = self._service(os.path.join(tmpdir, "vectors.db"))
            with self.assertRaises(PermissionError):
                service.reindex_knowledge("ceo_agent_v1")

    def test_default_api_exposes_provider_status_and_lexical_search(self):
        from fastapi.testclient import TestClient

        from app.main import create_app

        with patch.dict(os.environ, {}, clear=True):
            client = TestClient(create_app())
        providers = client.get("/models/providers")
        embeddings = client.get("/knowledge/embeddings/status")
        created = client.post(
            "/knowledge",
            json={"title": "Lexical API", "content": "Search remains available offline."},
        )
        searched = client.post(
            "/knowledge/search", json={"query": "Lexical API", "limit": 5}
        )
        forbidden = client.post(
            "/knowledge/embeddings/reindex", json={"actor_id": "ceo_agent_v1"}
        )

        self.assertEqual(providers.status_code, 200)
        self.assertEqual(providers.json()["default_provider"], "local")
        self.assertFalse(embeddings.json()["enabled"])
        self.assertEqual(searched.json()[0]["doc_id"], created.json()["doc_id"])
        self.assertEqual(forbidden.status_code, 403)


if __name__ == "__main__":
    unittest.main()
