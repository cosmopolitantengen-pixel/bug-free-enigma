from __future__ import annotations

from app.core.models import KnowledgeDoc


class KnowledgeBase:
    def __init__(self, docs: list[KnowledgeDoc] | None = None) -> None:
        self._docs: list[KnowledgeDoc] = list(docs or [])

    def write(self, doc: KnowledgeDoc) -> KnowledgeDoc:
        self._docs.append(doc)
        return doc

    def search(self, text: str) -> list[KnowledgeDoc]:
        needle = text.lower()
        return [
            doc
            for doc in self._docs
            if needle in doc.title.lower() or needle in doc.content.lower()
        ]

    def list(self) -> tuple[KnowledgeDoc, ...]:
        return tuple(self._docs)
