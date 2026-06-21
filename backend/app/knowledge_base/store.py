from __future__ import annotations

from collections.abc import Callable

from app.core.models import KnowledgeDoc


class KnowledgeBase:
    def __init__(self, docs: list[KnowledgeDoc] | None = None) -> None:
        self._docs: list[KnowledgeDoc] = list(docs or [])
        self._semantic_search: Callable[[str], list[KnowledgeDoc] | None] | None = None

    def write(self, doc: KnowledgeDoc) -> KnowledgeDoc:
        self._docs.append(doc)
        return doc

    def search(self, text: str) -> list[KnowledgeDoc]:
        lexical = self.lexical_search(text)
        if self._semantic_search is None:
            return lexical
        semantic = self._semantic_search(text)
        if semantic is None:
            return lexical
        merged: list[KnowledgeDoc] = []
        seen: set[str] = set()
        for doc in [*semantic, *lexical]:
            if doc.doc_id not in seen:
                merged.append(doc)
                seen.add(doc.doc_id)
        return merged

    def lexical_search(self, text: str) -> list[KnowledgeDoc]:
        needle = text.lower()
        return [
            doc
            for doc in self._docs
            if needle in doc.title.lower() or needle in doc.content.lower()
        ]

    def configure_semantic_search(
        self, callback: Callable[[str], list[KnowledgeDoc] | None] | None
    ) -> None:
        self._semantic_search = callback

    def list(self) -> tuple[KnowledgeDoc, ...]:
        return tuple(self._docs)
