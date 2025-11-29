"""Document format handlers for Anchor Text."""

from anchor_text.formats.base import FormatHandler
from anchor_text.formats.txt_handler import TXTHandler
from anchor_text.formats.docx_handler import DOCXHandler
from anchor_text.formats.pdf_handler import PDFHandler
from anchor_text.formats.odt_handler import ODTHandler
from anchor_text.formats.rtf_handler import RTFHandler
from anchor_text.formats.epub_handler import EPUBHandler

__all__ = [
    "FormatHandler",
    "TXTHandler",
    "DOCXHandler",
    "PDFHandler",
    "ODTHandler",
    "RTFHandler",
    "EPUBHandler",
]

# Map file extensions to handlers
HANDLER_MAP: dict[str, type[FormatHandler]] = {
    ".txt": TXTHandler,
    ".docx": DOCXHandler,
    ".pdf": PDFHandler,
    ".odt": ODTHandler,
    ".rtf": RTFHandler,
    ".epub": EPUBHandler,
}

SUPPORTED_EXTENSIONS = tuple(HANDLER_MAP.keys())


def get_handler(extension: str) -> type[FormatHandler]:
    """Get the appropriate handler class for a file extension."""
    ext = extension.lower()
    if ext not in HANDLER_MAP:
        raise ValueError(
            f"Unsupported file format: {ext}. "
            f"Supported formats: {', '.join(SUPPORTED_EXTENSIONS)}"
        )
    return HANDLER_MAP[ext]
