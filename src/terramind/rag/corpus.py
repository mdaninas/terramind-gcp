"""Strict Markdown metadata and heading-aware, character-bounded chunks."""

import hashlib
import re
from pathlib import Path

from pydantic import ValidationError

from terramind.errors import InputError
from terramind.rag.contracts import MAX_CHUNKS, Chunk, Document

MAX_DOCUMENT_BYTES = 48 * 1024
TARGET_CHARACTERS = 1800  # Roughly 450 English tokens, not a tokenizer guarantee.
OVERLAP_CHARACTERS = 160
SECRET = re.compile(
    r"-----BEGIN (?:[A-Z]+ )?PRIVATE KEY-----|\bAIza[\w-]{30,}|\bya29\.[\w-]+|"
    r"\b(?:ghp_|github_pat_)[\w]+|\bBearer\s+[A-Za-z0-9._-]{12,}",
    re.I,
)


def load_corpus(root: Path) -> tuple[Document, ...]:
    try:
        paths = sorted((*root.glob("runbooks/*.md"), *root.glob("incidents/*.md")))
        if not 8 <= len(paths) <= 12:
            raise InputError("Synthetic corpus must contain 8 to 12 Markdown documents")
        documents = []
        for path in paths:
            if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
                raise InputError("Knowledge source must remain inside the corpus")
            with path.open("rb") as stream:
                raw = stream.read(MAX_DOCUMENT_BYTES + 1)
            if len(raw) > MAX_DOCUMENT_BYTES:
                raise InputError("Knowledge document exceeds its size limit")
            text = raw.decode("utf-8").replace("\r\n", "\n")
            if SECRET.search(text):
                raise InputError("Knowledge source contains a credential marker")
            parts = text.split("---\n", 2)
            if len(parts) != 3 or parts[0] or not parts[2].strip():
                raise InputError("Knowledge document requires strict front matter")
            metadata: dict[str, str] = {}
            for line in parts[1].splitlines():
                key, separator, value = line.partition(": ")
                if not separator or key in metadata:
                    raise InputError("Invalid knowledge metadata")
                metadata[key] = value.strip()
            if set(metadata) != {"doc_id", "title", "version", "synthetic"}:
                raise InputError("Knowledge metadata has unexpected fields")
            if metadata.pop("synthetic") != "true":
                raise InputError("Only explicitly synthetic knowledge is supported")
            documents.append(
                Document(
                    doc_id=metadata["doc_id"],
                    title=metadata["title"],
                    version=metadata["version"],
                    source_path=path.relative_to(root).as_posix(),
                    content_hash=hashlib.sha256(parts[2].strip().encode()).hexdigest(),
                    body=parts[2].strip(),
                )
            )
        if len({doc.doc_id for doc in documents}) != len(documents):
            raise InputError("Knowledge document IDs must be unique")
        return tuple(documents)
    except (OSError, UnicodeError, ValidationError):
        raise InputError("Unable to load valid synthetic knowledge") from None


def chunk_document(document: Document) -> tuple[Chunk, ...]:
    sections: list[tuple[str, str]] = []
    heading = "overview"
    lines: list[str] = []
    seen: set[str] = set()
    in_code = False
    for line in document.body.splitlines():
        if line.startswith("```"):
            in_code = not in_code
        match = re.match(r"^#{1,6} (.+)$", line) if not in_code else None
        if match:
            if lines and "\n".join(lines).strip():
                sections.append((heading, "\n".join(lines).strip()))
            heading = re.sub(r"[^a-z0-9]+", "-", match[1].lower()).strip("-")[:60]
            if not heading or heading in seen:
                raise InputError("Knowledge headings must have unique nonempty slugs")
            seen.add(heading)
            lines = [line]
        else:
            lines.append(line)
    if lines and "\n".join(lines).strip():
        sections.append((heading, "\n".join(lines).strip()))
    chunks = []
    for section, content in sections:
        start = 0
        part = 0
        while start < len(content):
            end = min(start + TARGET_CHARACTERS, len(content))
            if end < len(content):
                boundary = content.rfind(" ", start + TARGET_CHARACTERS // 2, end)
                if boundary > start:
                    end = boundary
            text = content[start:end].strip()
            section_id = f"{section}-{part:03d}"
            chunks.append(
                Chunk(
                    chunk_id=hashlib.sha256(f"{document.doc_id}:{section_id}".encode()).hexdigest(),
                    doc_id=document.doc_id,
                    title=document.title,
                    version=document.version,
                    source_path=document.source_path,
                    content_hash=document.content_hash,
                    section_id=section_id,
                    chunk_hash=hashlib.sha256(text.encode()).hexdigest(),
                    text=text,
                )
            )
            if end == len(content):
                break
            start = max(start + 1, end - OVERLAP_CHARACTERS)
            part += 1
    return tuple(chunks)


def corpus_chunks(documents: tuple[Document, ...]) -> tuple[Chunk, ...]:
    chunks = tuple(chunk for document in documents for chunk in chunk_document(document))
    if not chunks or len(chunks) > MAX_CHUNKS:
        raise InputError("Knowledge corpus exceeds the chunk limit")
    return chunks
