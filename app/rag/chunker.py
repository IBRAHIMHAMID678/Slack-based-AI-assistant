"""Heading-aware text chunker with sentence boundary preservation.

Implements token-bounded chunking (400-token target, 60-token overlap),
zero-width character stripping, whitespace normalization, and hierarchical
heading path extraction for high-precision semantic retrieval.
"""

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Chunk:
    """Represents an indexed semantic chunk with rich metadata."""

    text: str
    metadata: dict[str, Any] = field(default_factory=dict)
    chunk_index: int = 0
    token_count: int = 0


ZERO_WIDTH_PATTERN = re.compile(r"[\u200B-\u200D\uFEFF\u202A-\u202E]")
SENTENCE_SPLIT_PATTERN = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'\(])")
ABBREVIATIONS = ["Dr.", "Mr.", "Mrs.", "Ms.", "Prof.", "vs.", "e.g.", "i.e.", "etc."]


def clean_untrusted_text(text: str) -> str:
    """Normalize text and strip zero-width or non-printable control characters."""
    if not text:
        return ""
    # Strip zero-width Unicode characters
    cleaned = ZERO_WIDTH_PATTERN.sub("", text)
    # Normalize carriage returns and excessive tabs
    cleaned = cleaned.replace("\r\n", "\n").replace("\r", "\n")
    # Normalize multiple consecutive blank lines into double newlines
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def estimate_tokens(text: str) -> int:
    """Estimate token count using 1 token ≈ 4 characters or 0.75 words."""
    words = len(text.split())
    chars = len(text)
    return max(words, chars // 4)


def is_heading(line: str) -> bool:
    """Determine if a text line represents a section heading."""
    stripped = line.strip()
    if not stripped or len(stripped) > 100:
        return False
    if stripped.startswith(("#", "==", "--")):
        return True
    if stripped.startswith("PROPOSAL"):
        return True
    # Uppercase headings like EXECUTIVE SUMMARY, PROPOSED SOLUTION
    if stripped.isupper() and len(stripped) >= 3 and not stripped.endswith((".", ":", ";")):
        return True
    return False


def split_into_sentences(text: str) -> list[str]:
    """Split text into complete sentences without breaking mid-sentence."""
    text = text.strip()
    if not text:
        return []
    processed = text
    for i, abb in enumerate(ABBREVIATIONS):
        processed = processed.replace(abb, f"__ABB_{i}__")

    candidates = SENTENCE_SPLIT_PATTERN.split(processed)
    sentences: list[str] = []
    for c in candidates:
        if c.strip():
            restored = c.strip()
            for i, abb in enumerate(ABBREVIATIONS):
                restored = restored.replace(f"__ABB_{i}__", abb)
            sentences.append(restored)
    return sentences if sentences else [text]


class HeadingAwareChunker:
    """Chunker that segments documents by headings and token boundaries."""

    def __init__(self, target_tokens: int = 400, overlap_tokens: int = 60) -> None:
        self.target_tokens = target_tokens
        self.overlap_tokens = overlap_tokens

    def chunk_document(
        self,
        raw_text: str,
        source_id: str,
        source_type: str = "proposal",
        industry: str | None = None,
        extra_metadata: dict[str, Any] | None = None,
    ) -> list[Chunk]:
        """Chunk a document while preserving headings and sentence boundaries."""
        cleaned_text = clean_untrusted_text(raw_text)
        lines = cleaned_text.splitlines()

        sections: list[dict[str, Any]] = []
        current_heading = "Overview"
        current_lines: list[str] = []

        for line in lines:
            if is_heading(line):
                if current_lines:
                    sections.append(
                        {
                            "heading": current_heading,
                            "content": "\n".join(current_lines).strip(),
                        }
                    )
                    current_lines = []
                current_heading = line.strip().lstrip("#").strip()
            else:
                current_lines.append(line)

        if current_lines:
            sections.append(
                {
                    "heading": current_heading,
                    "content": "\n".join(current_lines).strip(),
                }
            )

        chunks: list[Chunk] = []
        chunk_idx = 0

        for sec in sections:
            heading = sec["heading"]
            content = sec["content"]
            if not content:
                continue

            sentences = split_into_sentences(content)
            current_chunk_sentences: list[str] = []
            current_chunk_tokens = 0

            for sentence in sentences:
                sent_tokens = estimate_tokens(sentence)
                if (
                    current_chunk_tokens + sent_tokens > self.target_tokens
                    and current_chunk_sentences
                ):
                    chunk_text = f"## {heading}\n" + " ".join(current_chunk_sentences)
                    meta = {
                        "source_id": source_id,
                        "source_type": source_type,
                        "industry": industry or "general",
                        "heading_path": heading,
                        "chunk_index": chunk_idx,
                    }
                    if extra_metadata:
                        meta.update(extra_metadata)

                    chunks.append(
                        Chunk(
                            text=chunk_text,
                            metadata=meta,
                            chunk_index=chunk_idx,
                            token_count=estimate_tokens(chunk_text),
                        )
                    )
                    chunk_idx += 1

                    # Compute overlap sentences
                    overlap_sentences: list[str] = []
                    overlap_tokens_accum = 0
                    for rev_s in reversed(current_chunk_sentences):
                        s_tokens = estimate_tokens(rev_s)
                        if overlap_tokens_accum + s_tokens <= self.overlap_tokens:
                            overlap_sentences.insert(0, rev_s)
                            overlap_tokens_accum += s_tokens
                        else:
                            break

                    current_chunk_sentences = overlap_sentences + [sentence]
                    current_chunk_tokens = overlap_tokens_accum + sent_tokens
                else:
                    current_chunk_sentences.append(sentence)
                    current_chunk_tokens += sent_tokens

            if current_chunk_sentences:
                chunk_text = f"## {heading}\n" + " ".join(current_chunk_sentences)
                meta = {
                    "source_id": source_id,
                    "source_type": source_type,
                    "industry": industry or "general",
                    "heading_path": heading,
                    "chunk_index": chunk_idx,
                }
                if extra_metadata:
                    meta.update(extra_metadata)

                chunks.append(
                    Chunk(
                        text=chunk_text,
                        metadata=meta,
                        chunk_index=chunk_idx,
                        token_count=estimate_tokens(chunk_text),
                    )
                )
                chunk_idx += 1

        return chunks
