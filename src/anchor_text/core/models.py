"""Core data models for Anchor Text.

Re-exports the IR models for convenience.
"""

from anchor_text.formatting.ir import (
    TextStyle,
    TextRun,
    TextBlock,
    ImageRef,
    FormattedDocument,
)

__all__ = [
    "TextStyle",
    "TextRun",
    "TextBlock",
    "ImageRef",
    "FormattedDocument",
]
