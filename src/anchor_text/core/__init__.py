"""Core transformation logic for Anchor Text."""

from anchor_text.core.models import TextRun, TextBlock, FormattedDocument, ImageRef
from anchor_text.core.transformer import TextTransformer
from anchor_text.core.scaffolding import ScaffoldingContext, FadingProfile

__all__ = [
    "TextRun",
    "TextBlock",
    "FormattedDocument",
    "ImageRef",
    "TextTransformer",
    "ScaffoldingContext",
    "FadingProfile",
]
