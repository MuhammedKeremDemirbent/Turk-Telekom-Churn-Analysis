"""reference_material.json.gz veri okuyucusu."""

from collections import defaultdict
import gzip
import json
from pathlib import Path
import re
from typing import Iterator

from .models import Document


TITLE_PATTERN = re.compile(r"^#\s+(.+)$", re.MULTILINE)
CATEGORY_PATTERN = re.compile(r"\*\*Kategori:\*\*\s*(.+)")
ISSUE_PATTERN = re.compile(r"'([^']+)'\s+sorununun")


def iter_json_objects(text: str) -> Iterator[dict[str, object]]:
    """
    Art arda yazılmış JSON nesnelerini okur.

    Veri dosyası standart JSON listesi veya JSONL olmadığı için
    json.load() doğrudan kullanılamaz.
    """
    decoder = json.JSONDecoder()
    position = 0

    while position < len(text):
        match = re.search(r"\S", text[position:])

        if match is None:
            return

        position += match.start()
        value, position = decoder.raw_decode(text, position)

        if not isinstance(value, dict):
            raise ValueError("Her veri kaydı bir JSON nesnesi olmalıdır.")

        yield value


def extract_value(pattern: re.Pattern[str], text: str) -> str:
    match = pattern.search(text)
    return match.group(1).strip() if match else ""


def load_documents(
    path: str | Path,
    deduplicate: bool = True,
) -> list[Document]:
    path = Path(path)

    if not path.exists():
        raise FileNotFoundError(f"Veri dosyası bulunamadı: {path}")

    with gzip.open(path, "rt", encoding="utf-8") as file:
        records = list(iter_json_objects(file.read()))

    documents: list[Document] = []

    for record_number, record in enumerate(records, start=1):
        document_id = record.get("document_id")
        content = record.get("content")

        if not isinstance(document_id, str) or not document_id.strip():
            raise ValueError(
                f"{record_number}. kayıtta geçerli document_id bulunamadı."
            )

        if not isinstance(content, str) or not content.strip():
            raise ValueError(
                f"{record_number}. kayıtta geçerli content bulunamadı."
            )

        content = content.strip()

        documents.append(
            Document(
                document_id=document_id.strip(),
                content=content,
                title=extract_value(TITLE_PATTERN, content),
                category=extract_value(CATEGORY_PATTERN, content),
                issue_code=extract_value(ISSUE_PATTERN, content),
            )
        )

    if not deduplicate:
        return documents

    groups: dict[str, list[Document]] = defaultdict(list)

    for document in documents:
        groups[document.content].append(document)

    unique_documents: list[Document] = []

    for group in groups.values():
        first_document = group[0]

        unique_documents.append(
            Document(
                document_id=first_document.document_id,
                content=first_document.content,
                title=first_document.title,
                category=first_document.category,
                issue_code=first_document.issue_code,
                duplicate_ids=tuple(
                    document.document_id for document in group[1:]
                ),
            )
        )

    return unique_documents