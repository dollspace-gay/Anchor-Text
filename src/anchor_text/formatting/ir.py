"""Intermediate Representation for formatted text.

This module defines the data structures that bridge AI markdown output
to format-specific rendering. The IR allows consistent handling of
formatted text across all document formats.
"""

from dataclasses import dataclass, field
from enum import Flag, auto
from pathlib import Path
from typing import Optional


class TextStyle(Flag):
    """Text styling flags (combinable with |)."""

    NONE = 0
    BOLD = auto()
    ITALIC = auto()


@dataclass
class TextRun:
    """A contiguous run of text with consistent styling.

    Attributes:
        text: The text content
        style: Combined style flags (BOLD, ITALIC, or both)
    """

    text: str
    style: TextStyle = TextStyle.NONE

    @property
    def bold(self) -> bool:
        """Check if this run is bold."""
        return TextStyle.BOLD in self.style

    @property
    def italic(self) -> bool:
        """Check if this run is italic."""
        return TextStyle.ITALIC in self.style

    def __str__(self) -> str:
        return self.text


@dataclass
class ImageRef:
    """Reference to an image extracted from a document.

    Attributes:
        data: Raw image bytes
        format: Image format (png, jpg, etc.)
        width: Original width in pixels (if known)
        height: Original height in pixels (if known)
        page: Page number where image appeared (for PDFs)
        position: Approximate position in text flow (index in blocks list)
    """

    data: bytes
    format: str = "png"
    width: Optional[int] = None
    height: Optional[int] = None
    page: Optional[int] = None
    position: int = 0

    def save(self, path: Path) -> None:
        """Save image data to a file."""
        path.write_bytes(self.data)


@dataclass
class TextBlock:
    """A paragraph/block of text containing multiple styled runs.

    Attributes:
        runs: List of TextRun objects making up this block
        is_decoder_trap: Whether this block is the Decoder's Trap question
    """

    runs: list[TextRun] = field(default_factory=list)
    is_decoder_trap: bool = False

    @property
    def plain_text(self) -> str:
        """Get the plain text content without styling."""
        return "".join(run.text for run in self.runs)

    def append(self, text: str, style: TextStyle = TextStyle.NONE) -> None:
        """Append a new run to this block."""
        self.runs.append(TextRun(text=text, style=style))

    def __str__(self) -> str:
        return self.plain_text


@dataclass
class FormattedDocument:
    """Complete formatted document ready for rendering.

    Attributes:
        blocks: List of text blocks (paragraphs)
        images: List of images extracted from the original document
        metadata: Additional metadata from the original document
    """

    blocks: list[TextBlock] = field(default_factory=list)
    images: list[ImageRef] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    @property
    def plain_text(self) -> str:
        """Get all text content without styling."""
        return "\n\n".join(block.plain_text for block in self.blocks)

    @property
    def has_decoder_trap(self) -> bool:
        """Check if document contains a Decoder's Trap."""
        return any(block.is_decoder_trap for block in self.blocks)

    def add_block(self, block: TextBlock) -> None:
        """Add a text block to the document."""
        self.blocks.append(block)

    def add_image(self, image: ImageRef) -> None:
        """Add an image reference to the document."""
        self.images.append(image)
