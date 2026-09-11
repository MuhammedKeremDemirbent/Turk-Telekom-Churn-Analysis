from dataclasses import dataclass, field


@dataclass(frozen=True)
class Document:
    document_id: str
    content: str
    title: str = ""
    category: str = ""
    issue_code: str = ""
    duplicate_ids: tuple[str, ...] = field(default_factory=tuple)

@dataclass(frozen=True)
class SearchResult:
    document: Document
    score: float