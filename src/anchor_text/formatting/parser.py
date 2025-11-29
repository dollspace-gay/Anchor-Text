"""Markdown parser for converting AI output to IR."""

import re
from typing import Optional

from anchor_text.formatting.ir import (
    TextStyle,
    TextRun,
    TextBlock,
    FormattedDocument,
    ImageRef,
)


class MarkdownParser:
    """Parse markdown formatting into structured IR."""

    # Regex patterns for markdown
    # Order matters: check bold-italic first, then bold, then italic
    BOLD_ITALIC_PATTERN = re.compile(r"\*\*\*(.+?)\*\*\*")
    BOLD_PATTERN = re.compile(r"\*\*(.+?)\*\*")
    ITALIC_PATTERN = re.compile(r"\*([^*]+?)\*")

    # Pattern to detect Decoder's Trap
    DECODER_TRAP_PATTERN = re.compile(
        r"\[Decoder\s*Check:.*?\]|DECODER'S\s*TRAP:.*|Decoder's\s*Trap:.*",
        re.IGNORECASE | re.DOTALL,
    )

    def parse(
        self,
        markdown_text: str,
        images: Optional[list[ImageRef]] = None,
        metadata: Optional[dict] = None,
    ) -> FormattedDocument:
        """Convert markdown text to FormattedDocument.

        Args:
            markdown_text: The markdown-formatted text from the AI
            images: Optional list of images from original document
            metadata: Optional metadata from original document

        Returns:
            FormattedDocument with parsed blocks
        """
        doc = FormattedDocument(
            images=images or [],
            metadata=metadata or {},
        )

        # Split into paragraphs (blank lines)
        paragraphs = re.split(r"\n\s*\n", markdown_text.strip())

        for para in paragraphs:
            if not para.strip():
                continue

            # Handle multi-line paragraphs (single newlines within)
            lines = para.strip().split("\n")

            for line in lines:
                line = line.strip()
                if not line:
                    continue

                block = self._parse_line(line)

                # Check if this is the Decoder's Trap
                if self.DECODER_TRAP_PATTERN.search(line):
                    block.is_decoder_trap = True

                doc.add_block(block)

        return doc

    def _parse_line(self, line: str) -> TextBlock:
        """Parse a single line into a TextBlock with styled runs."""
        block = TextBlock()
        self._parse_into_runs(line, block)
        return block

    def _parse_into_runs(self, text: str, block: TextBlock) -> None:
        """Parse text and add runs to block, handling nested formatting."""
        if not text:
            return

        # Find all formatting markers and their positions
        segments = self._tokenize_markdown(text)

        for segment_text, style in segments:
            if segment_text:
                block.runs.append(TextRun(text=segment_text, style=style))

    def _tokenize_markdown(self, text: str) -> list[tuple[str, TextStyle]]:
        """Tokenize markdown into (text, style) pairs.

        Handles:
        - ***bold italic***
        - **bold**
        - *italic*
        - plain text
        """
        segments: list[tuple[str, TextStyle]] = []
        pos = 0

        while pos < len(text):
            # Check for bold-italic (***)
            if text[pos : pos + 3] == "***":
                # Find closing ***
                end = text.find("***", pos + 3)
                if end != -1:
                    content = text[pos + 3 : end]
                    segments.append(
                        (content, TextStyle.BOLD | TextStyle.ITALIC)
                    )
                    pos = end + 3
                    continue
                # No closing found, treat as plain text
                pass

            # Check for bold (**)
            if text[pos : pos + 2] == "**":
                # Find closing **
                end = text.find("**", pos + 2)
                if end != -1:
                    content = text[pos + 2 : end]
                    segments.append((content, TextStyle.BOLD))
                    pos = end + 2
                    continue
                # No closing found, treat as plain text
                pass

            # Check for italic (*)
            if text[pos] == "*" and (pos + 1 < len(text) and text[pos + 1] != "*"):
                # Find closing *
                end = pos + 1
                while end < len(text):
                    if text[end] == "*" and (
                        end + 1 >= len(text) or text[end + 1] != "*"
                    ):
                        break
                    end += 1
                if end < len(text):
                    content = text[pos + 1 : end]
                    segments.append((content, TextStyle.ITALIC))
                    pos = end + 1
                    continue
                # No closing found, treat as plain text
                pass

            # Plain text - find next formatting marker
            next_marker = len(text)
            for marker in ["***", "**", "*"]:
                idx = text.find(marker, pos)
                if idx != -1 and idx < next_marker:
                    next_marker = idx

            # Add plain text segment (at least one character)
            end_pos = next_marker if next_marker > pos else pos + 1
            segments.append((text[pos:end_pos], TextStyle.NONE))
            pos = end_pos

        return segments

    def to_plain_text(self, doc: FormattedDocument) -> str:
        """Convert a FormattedDocument back to plain text."""
        return doc.plain_text

    def to_markdown(self, doc: FormattedDocument) -> str:
        """Convert a FormattedDocument back to markdown."""
        lines: list[str] = []

        for block in doc.blocks:
            line_parts: list[str] = []
            for run in block.runs:
                text = run.text
                if run.bold and run.italic:
                    text = f"***{text}***"
                elif run.bold:
                    text = f"**{text}**"
                elif run.italic:
                    text = f"*{text}*"
                line_parts.append(text)
            lines.append("".join(line_parts))

        return "\n\n".join(lines)
