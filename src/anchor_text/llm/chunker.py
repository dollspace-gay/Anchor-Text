"""Document chunking for handling large files within token limits."""

import re
from typing import Iterator

import tiktoken

from anchor_text.config import get_settings


class DocumentChunker:
    """Split documents into processable chunks respecting token limits."""

    def __init__(
        self,
        max_tokens: int | None = None,
        overlap_sentences: int = 2,
        encoding_name: str = "cl100k_base",
    ) -> None:
        """Initialize the document chunker.

        Args:
            max_tokens: Maximum tokens per chunk (default from settings)
            overlap_sentences: Number of sentences to overlap between chunks
            encoding_name: Tiktoken encoding name for token counting
        """
        settings = get_settings()
        self.max_tokens = max_tokens or settings.max_chunk_tokens
        self.overlap_sentences = overlap_sentences
        self.encoder = tiktoken.get_encoding(encoding_name)

    def estimate_tokens(self, text: str) -> int:
        """Estimate token count for text."""
        return len(self.encoder.encode(text))

    def _split_sentences(self, text: str) -> list[str]:
        """Split text into sentences."""
        # Simple sentence splitting - handles common cases
        # Preserves sentence-ending punctuation
        sentences = re.split(r"(?<=[.!?])\s+", text)
        return [s.strip() for s in sentences if s.strip()]

    def _split_paragraphs(self, text: str) -> list[str]:
        """Split text into paragraphs."""
        paragraphs = re.split(r"\n\s*\n", text)
        return [p.strip() for p in paragraphs if p.strip()]

    def chunk_text(self, text: str) -> Iterator[tuple[str, bool, bool]]:
        """Split text into chunks suitable for LLM processing.

        Yields:
            Tuples of (chunk_text, is_first, is_last)

        The chunking strategy:
        1. First try to split on paragraph boundaries
        2. If a paragraph is too large, split on sentence boundaries
        3. Maintain overlap between chunks for context continuity
        """
        total_tokens = self.estimate_tokens(text)

        # If text fits in one chunk, return it directly
        if total_tokens <= self.max_tokens:
            yield (text, True, True)
            return

        paragraphs = self._split_paragraphs(text)
        chunks: list[str] = []
        current_chunk: list[str] = []
        current_tokens = 0
        overlap_buffer: list[str] = []

        for para in paragraphs:
            para_tokens = self.estimate_tokens(para)

            # If single paragraph exceeds limit, split by sentences
            if para_tokens > self.max_tokens:
                # Flush current chunk first
                if current_chunk:
                    chunks.append("\n\n".join(current_chunk))
                    # Keep last sentences for overlap
                    last_para = current_chunk[-1] if current_chunk else ""
                    overlap_buffer = self._split_sentences(last_para)[
                        -self.overlap_sentences :
                    ]
                    current_chunk = []
                    current_tokens = 0

                # Split large paragraph by sentences
                sentences = self._split_sentences(para)
                sentence_chunk: list[str] = list(overlap_buffer)
                sentence_tokens = sum(
                    self.estimate_tokens(s) for s in sentence_chunk
                )

                for sentence in sentences:
                    sent_tokens = self.estimate_tokens(sentence)

                    if sentence_tokens + sent_tokens > self.max_tokens:
                        if sentence_chunk:
                            chunks.append(" ".join(sentence_chunk))
                            overlap_buffer = sentence_chunk[-self.overlap_sentences :]
                            sentence_chunk = list(overlap_buffer)
                            sentence_tokens = sum(
                                self.estimate_tokens(s) for s in sentence_chunk
                            )

                    sentence_chunk.append(sentence)
                    sentence_tokens += sent_tokens

                if sentence_chunk:
                    # Don't add to chunks yet, continue with normal flow
                    current_chunk = [" ".join(sentence_chunk)]
                    current_tokens = self.estimate_tokens(current_chunk[0])
                    overlap_buffer = sentence_chunk[-self.overlap_sentences :]

            elif current_tokens + para_tokens > self.max_tokens:
                # Current chunk is full, start new one
                if current_chunk:
                    chunks.append("\n\n".join(current_chunk))
                    # Keep last paragraph for overlap context
                    last_para = current_chunk[-1]
                    overlap_buffer = self._split_sentences(last_para)[
                        -self.overlap_sentences :
                    ]

                # Start new chunk with overlap
                if overlap_buffer:
                    overlap_text = " ".join(overlap_buffer)
                    current_chunk = [overlap_text, para]
                    current_tokens = self.estimate_tokens(
                        "\n\n".join(current_chunk)
                    )
                else:
                    current_chunk = [para]
                    current_tokens = para_tokens
            else:
                current_chunk.append(para)
                current_tokens += para_tokens

        # Don't forget the last chunk
        if current_chunk:
            chunks.append("\n\n".join(current_chunk))

        # Yield chunks with position flags
        for i, chunk in enumerate(chunks):
            is_first = i == 0
            is_last = i == len(chunks) - 1
            yield (chunk, is_first, is_last)

    def needs_chunking(self, text: str) -> bool:
        """Check if text needs to be chunked."""
        return self.estimate_tokens(text) > self.max_tokens
