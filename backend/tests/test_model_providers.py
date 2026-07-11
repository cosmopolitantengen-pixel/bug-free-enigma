import json
import os
import subprocess
import sys
import tempfile
import time
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
from app.models.gateway import ModelGateway, ModelPricing, create_model_gateway
from app.models.providers import (
    CodexCliProvider,
    DeepSeekChatProvider,
    ModelProviderConfigurationError,
    ModelProviderError,
    OpenAIResponsesProvider,
    ProviderGeneration,
    ProviderStreamEvent,
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


class _StreamingFakeProvider(_FakeModelProvider):
    def stream(self, prompt, model_name, purpose, max_output_tokens):
        yield ProviderStreamEvent(delta="real ")
        yield ProviderStreamEvent(delta="stream")
        yield ProviderStreamEvent(
            generation=ProviderGeneration(
                output="real stream",
                prompt_tokens=5,
                completion_tokens=2,
                total_tokens=7,
            )
        )


class _InterruptedStreamingProvider(_FakeModelProvider):
    def stream(self, prompt, model_name, purpose, max_output_tokens):
        yield ProviderStreamEvent(delta="partial")
        raise ModelProviderError("upstream disconnected")


class _SlowStreamingProvider(_StreamingFakeProvider):
    def stream(self, prompt, model_name, purpose, max_output_tokens):
        time.sleep(0.05)
        yield from super().stream(prompt, model_name, purpose, max_output_tokens)


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
    def test_model_pricing_preserves_sub_micro_costs(self):
        pricing = ModelPricing(input_per_million=0.14, output_per_million=0.28)
        self.assertEqual(pricing.estimate(1, 1), 0.00000042)

    def test_codex_cli_provider_uses_read_only_ephemeral_json_and_parses_usage(self):
        observed = {}

        def runner(command, **kwargs):
            observed["command"] = command
            observed.update(kwargs)
            return subprocess.CompletedProcess(
                command,
                0,
                stdout="\n".join(
                    (
                        '{"type":"thread.started","thread_id":"thread-test"}',
                        '{"type":"item.completed","item":{"type":"agent_message","text":"Codex answer"}}',
                        '{"type":"turn.completed","usage":{"input_tokens":14,"output_tokens":8}}',
                    )
                ),
                stderr="ignored diagnostic",
            )

        with tempfile.TemporaryDirectory() as workspace:
            provider = CodexCliProvider(
                "codex.cmd",
                workspace_root=workspace,
                runner=runner,
            )
            with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "must-not-leak"}):
                generation = provider.generate(
                    "Sensitive prompt", "codex-default", "unit_test", 512
                )

        self.assertEqual(generation.output, "Codex answer")
        self.assertEqual(generation.prompt_tokens, 14)
        self.assertEqual(generation.completion_tokens, 8)
        self.assertEqual(generation.total_tokens, 22)
        self.assertEqual(observed["command"][:2], ["codex.cmd", "exec"])
        self.assertIn("--ephemeral", observed["command"])
        self.assertIn("--ignore-user-config", observed["command"])
        self.assertIn("read-only", observed["command"])
        self.assertNotIn("--model", observed["command"])
        self.assertFalse(observed["shell"])
        self.assertNotIn("DEEPSEEK_API_KEY", observed["env"])
        self.assertIn("unit_test", observed["input"])
        self.assertIn("512", observed["input"])

    def test_codex_cli_provider_sanitizes_process_failures(self):
        def runner(command, **kwargs):
            return subprocess.CompletedProcess(
                command,
                7,
                stdout="",
                stderr="private upstream detail and secret token",
            )

        with tempfile.TemporaryDirectory() as workspace:
            provider = CodexCliProvider(
                "codex.cmd",
                workspace_root=workspace,
                runner=runner,
            )
            with self.assertRaisesRegex(ModelProviderError, "exit code 7") as raised:
                provider.generate("prompt", "codex-default", "unit_test", 128)

        self.assertNotIn("private upstream detail", str(raised.exception))
        self.assertNotIn("secret token", str(raised.exception))

    def test_codex_cli_provider_reports_usage_limit_without_upstream_links(self):
        def runner(command, **kwargs):
            return subprocess.CompletedProcess(
                command,
                1,
                stdout=(
                    '{"type":"error","message":"You have hit your usage limit. '
                    'Purchase credits at https://chatgpt.com/private"}'
                ),
                stderr="",
            )

        with tempfile.TemporaryDirectory() as workspace:
            provider = CodexCliProvider(
                "codex.cmd",
                workspace_root=workspace,
                runner=runner,
            )
            with self.assertRaisesRegex(ModelProviderError, "usage limit reached") as raised:
                provider.generate("prompt", "codex-default", "unit_test", 128)

        self.assertNotIn("chatgpt.com/private", str(raised.exception))

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

    def test_openai_responses_provider_streams_typed_text_events_and_usage(self):
        observed = {}

        def handler(request):
            observed["body"] = json.loads(request.content)
            events = [
                'event: response.output_text.delta\ndata: {"type":"response.output_text.delta","delta":"Hello "}',
                'event: response.output_text.delta\ndata: {"type":"response.output_text.delta","delta":"stream"}',
                'event: response.completed\ndata: {"type":"response.completed","response":{"usage":{"input_tokens":9,"output_tokens":2,"total_tokens":11}}}',
            ]
            return httpx.Response(
                200,
                request=request,
                headers={"content-type": "text/event-stream"},
                text="\n\n".join(events) + "\n\n",
            )

        provider = OpenAIResponsesProvider(
            "test-key",
            default_model="test-model",
            client=httpx.Client(
                base_url="https://api.openai.com/v1",
                transport=httpx.MockTransport(handler),
            ),
        )

        events = list(provider.stream("prompt", "test-model", "stream_test", 77))

        self.assertTrue(observed["body"]["stream"])
        self.assertFalse(observed["body"]["store"])
        self.assertEqual([event.delta for event in events if event.delta], ["Hello ", "stream"])
        self.assertEqual(events[-1].generation.output, "Hello stream")
        self.assertEqual(events[-1].generation.total_tokens, 11)

    def test_deepseek_chat_provider_parses_text_and_usage(self):
        observed = {}

        def handler(request):
            observed["path"] = request.url.path
            observed["authorization"] = request.headers.get("authorization")
            observed["body"] = json.loads(request.content)
            return httpx.Response(
                200,
                request=request,
                json={
                    "choices": [
                        {"message": {"role": "assistant", "content": "DeepSeek result"}}
                    ],
                    "usage": {
                        "prompt_tokens": 20,
                        "completion_tokens": 8,
                        "total_tokens": 28,
                    },
                },
            )

        provider = DeepSeekChatProvider(
            "deepseek-test-key",
            default_model="deepseek-v4-flash",
            client=httpx.Client(
                base_url="https://api.deepseek.com",
                headers={"Authorization": "Bearer deepseek-test-key"},
                transport=httpx.MockTransport(handler),
            ),
        )

        result = provider.generate(
            "Sensitive prompt", "deepseek-v4-flash", "unit_test", 456
        )

        self.assertEqual(observed["path"], "/chat/completions")
        self.assertEqual(observed["authorization"], "Bearer deepseek-test-key")
        self.assertEqual(observed["body"]["model"], "deepseek-v4-flash")
        self.assertEqual(observed["body"]["messages"][-1]["content"], "Sensitive prompt")
        self.assertFalse(observed["body"]["stream"])
        self.assertEqual(observed["body"]["max_tokens"], 456)
        self.assertEqual(result.output, "DeepSeek result")
        self.assertEqual(result.total_tokens, 28)

    def test_deepseek_provider_sanitizes_http_errors(self):
        def handler(request):
            return httpx.Response(
                429,
                request=request,
                headers={"x-request-id": "ds_req_test"},
                json={"error": {"message": "private upstream detail"}},
            )

        provider = DeepSeekChatProvider(
            "deepseek-test-key",
            client=httpx.Client(
                base_url="https://api.deepseek.com",
                transport=httpx.MockTransport(handler),
            ),
        )

        with self.assertRaisesRegex(ModelProviderError, "HTTP 429.*ds_req_test") as raised:
            provider.generate("prompt", "deepseek-v4-flash", "unit_test", 100)
        self.assertNotIn("private upstream detail", str(raised.exception))

    def test_deepseek_provider_streams_deltas_and_final_usage(self):
        observed = {}

        def handler(request):
            observed["body"] = json.loads(request.content)
            chunks = [
                'data: {"choices":[{"delta":{"content":"Deep"}}],"usage":null}',
                'data: {"choices":[{"delta":{"content":"Seek"}}],"usage":null}',
                'data: {"choices":[],"usage":{"prompt_tokens":8,"completion_tokens":2,"total_tokens":10}}',
                "data: [DONE]",
            ]
            return httpx.Response(
                200,
                request=request,
                headers={"content-type": "text/event-stream"},
                text="\n\n".join(chunks) + "\n\n",
            )

        provider = DeepSeekChatProvider(
            "deepseek-test-key",
            client=httpx.Client(
                base_url="https://api.deepseek.com",
                transport=httpx.MockTransport(handler),
            ),
        )

        events = list(
            provider.stream("prompt", "deepseek-v4-flash", "stream_test", 88)
        )

        self.assertTrue(observed["body"]["stream"])
        self.assertTrue(observed["body"]["stream_options"]["include_usage"])
        self.assertEqual([event.delta for event in events if event.delta], ["Deep", "Seek"])
        self.assertEqual(events[-1].generation.output, "DeepSeek")
        self.assertEqual(events[-1].generation.total_tokens, 10)

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

    def test_gateway_emits_stream_deltas_and_records_one_usage(self):
        gateway = ModelGateway(
            providers={"fake": _StreamingFakeProvider()}, default_provider="fake"
        )
        deltas = []

        response = gateway.generate(
            "Private model input",
            actor_id="document_agent_v1",
            purpose="stream_test",
            on_delta=deltas.append,
        )

        self.assertEqual(deltas, ["real ", "stream"])
        self.assertEqual(response.output, "real stream")
        self.assertEqual(response.usage.total_tokens, 7)
        self.assertEqual(len(gateway.list_usage()), 1)

    def test_gateway_does_not_mix_fallback_after_partial_stream_output(self):
        gateway = ModelGateway(
            providers={
                "primary": _InterruptedStreamingProvider(),
                "backup": _StreamingFakeProvider(),
            },
            default_provider="primary",
            fallback_order=("backup",),
        )
        deltas = []

        with self.assertRaisesRegex(ModelProviderError, "interrupted after partial"):
            gateway.generate(
                "Private model input",
                actor_id="document_agent_v1",
                purpose="stream_test",
                on_delta=deltas.append,
            )

        self.assertEqual(deltas, ["partial"])
        self.assertEqual(gateway.list_usage(), [])

    def test_chat_stream_finishes_persistence_after_consumer_disconnect(self):
        gateway = ModelGateway(
            providers={"fake": _SlowStreamingProvider()}, default_provider="fake"
        )
        service = CompanyApplicationService(
            company_os=build_company_os(model_gateway=gateway)
        )
        session = service.create_chat_session()
        stream = service.stream_chat_session_message(
            session["session_id"],
            "Keep working after the browser leaves.",
            mode="chat",
            provider="fake",
        )

        self.assertEqual(next(stream)["event"], "ready")
        stream.close()
        for _ in range(50):
            if len(service.list_chat_sessions()[0]["messages"]) == 2:
                break
            time.sleep(0.01)

        stored = service.list_chat_sessions()[0]
        self.assertEqual(len(stored["messages"]), 2)
        self.assertEqual(stored["messages"][-1]["content"], "real stream")
        self.assertEqual(len(service.list_model_usage()), 1)

    def test_gateway_falls_back_and_records_actual_provider_pricing(self):
        gateway = ModelGateway(
            providers={
                "primary": _FailingModelProvider(),
                "backup": _FakeModelProvider(),
            },
            default_provider="primary",
            fallback_order=("backup",),
            pricing={
                "backup": {
                    "fake-model-v1": ModelPricing(
                        input_per_million=1.0,
                        output_per_million=2.0,
                    )
                }
            },
        )

        response = gateway.generate(
            "Fallback input",
            actor_id="document_agent_v1",
            purpose="fallback_test",
        )

        self.assertTrue(response.fallback_used)
        self.assertEqual(response.requested_provider, "primary")
        self.assertEqual(response.attempted_providers, ("primary", "backup"))
        self.assertEqual(response.usage.provider, "backup")
        self.assertEqual(response.usage.estimated_cost, 0.000025)
        status = gateway.provider_status()
        self.assertEqual(status["fallback_order"], ["backup"])
        self.assertEqual(
            status["provider_details"]["backup"]["pricing_usd_per_million"]
            ["fake-model-v1"]["output"],
            2.0,
        )

    def test_service_exposes_fallback_routing(self):
        gateway = ModelGateway(
            providers={
                "primary": _FailingModelProvider(),
                "backup": _FakeModelProvider(),
            },
            default_provider="primary",
            fallback_order=("backup",),
        )
        service = CompanyApplicationService(
            company_os=build_company_os(model_gateway=gateway)
        )

        result = service.generate_model_response(
            prompt="Fallback service test",
            actor_id="document_agent_v1",
            purpose="fallback_test",
        )

        self.assertFalse(result["blocked"])
        self.assertTrue(result["routing"]["fallback_used"])
        self.assertEqual(result["routing"]["actual_provider"], "backup")
        self.assertEqual(
            service.list_audit_logs()[-1]["result"], "model fallback used"
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

    def test_model_factory_configures_deepseek_models_pricing_and_fallback(self):
        with patch.dict(
            os.environ,
            {
                "DEEPSEEK_API_KEY": "deepseek-test-key",
                "AI_COMPANY_OS_MODEL_PROVIDER": "deepseek",
                "AI_COMPANY_OS_MODEL_FALLBACKS": "local",
            },
            clear=True,
        ):
            gateway = create_model_gateway()

        status = gateway.provider_status()
        self.assertEqual(status["default_provider"], "deepseek")
        self.assertEqual(status["fallback_order"], ["local"])
        self.assertEqual(
            status["allowed_models"]["deepseek"],
            ["deepseek-v4-flash", "deepseek-v4-pro"],
        )
        self.assertEqual(
            status["provider_details"]["deepseek"]["pricing_usd_per_million"]
            ["deepseek-v4-pro"]["input"],
            0.435,
        )

    def test_model_factory_configures_codex_as_governed_local_core(self):
        with tempfile.TemporaryDirectory() as workspace:
            with patch.dict(
                os.environ,
                {
                    "AI_COMPANY_OS_ENABLE_CODEX_CLI": "1",
                    "AI_COMPANY_OS_CODEX_EXECUTABLE": "codex.cmd",
                    "AI_COMPANY_OS_CODEX_WORKSPACE_ROOT": workspace,
                    "AI_COMPANY_OS_MODEL_PROVIDER": "codex",
                },
                clear=True,
            ):
                gateway = create_model_gateway()

        status = gateway.provider_status()
        self.assertEqual(status["default_provider"], "codex")
        self.assertEqual(status["allowed_models"]["codex"], ["codex-default"])
        self.assertEqual(
            status["provider_details"]["codex"]["sandbox"], "read-only"
        )
        self.assertEqual(
            status["provider_details"]["codex"]["pricing_usd_per_million"]
            ["codex-default"]["input"],
            0,
        )
        self.assertTrue(
            status["provider_details"]["codex"]["governed_execution"]
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
