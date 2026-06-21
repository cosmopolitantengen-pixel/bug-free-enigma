import os
import sys
import unittest
import uuid


BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.core.models import KnowledgeDoc
from app.persistence.postgres_store import POSTGRES_SCHEMA_VERSION, PostgresStateStore


POSTGRES_TEST_URL = os.getenv("AI_COMPANY_OS_TEST_POSTGRES_URL")


@unittest.skipUnless(
    POSTGRES_TEST_URL,
    "set AI_COMPANY_OS_TEST_POSTGRES_URL to run PostgreSQL/pgvector integration tests",
)
class PostgresIntegrationTests(unittest.TestCase):
    def test_schema_guards_and_pgvector_round_trip(self):
        store = PostgresStateStore(POSTGRES_TEST_URL)
        doc = KnowledgeDoc(
            title="PostgreSQL integration fixture",
            content="Dedicated test database record.",
            doc_id=f"integration-{uuid.uuid4()}",
        )
        embedding = [0.0] * 1536
        embedding[0] = 1.0

        try:
            store.save_knowledge(doc)
            store.upsert_knowledge_embedding(doc.doc_id, embedding, {"test": True})
            self.assertIn(doc.doc_id, store.list_knowledge_embedding_doc_ids())
            matches = store.search_knowledge_embeddings(embedding, limit=1)

            self.assertEqual(store.schema_version(), POSTGRES_SCHEMA_VERSION)
            self.assertTrue(store.audit_append_only_guards_enabled())
            self.assertEqual(matches[0]["doc_id"], doc.doc_id)
            self.assertGreater(matches[0]["score"], 0.99)
        finally:
            with store._connect() as connection:
                connection.execute(
                    "DELETE FROM knowledge_embeddings WHERE doc_id = %s",
                    (doc.doc_id,),
                )
                connection.execute(
                    "DELETE FROM knowledge_docs WHERE record_id = %s",
                    (doc.doc_id,),
                )


if __name__ == "__main__":
    unittest.main()
