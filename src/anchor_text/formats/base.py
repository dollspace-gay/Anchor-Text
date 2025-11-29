"""Abstract base class for document format handlers."""

from abc import ABC, abstractmethod
from pathlib import Path

from anchor_text.formatting.ir import FormattedDocument, ImageRef


class FormatHandler(ABC):
    """Abstract base class for document format handlers.

    Each handler must implement reading plain text from a document,
    writing formatted text back to the document format, and
    optionally extracting images.
    """

    @property
    @abstractmethod
    def supported_extensions(self) -> tuple[str, ...]:
        """Return tuple of supported file extensions (e.g., ('.pdf',))."""
        ...

    @abstractmethod
    def read(self, path: Path) -> str:
        """Extract plain text from document.

        Args:
            path: Path to the input document

        Returns:
            Plain text content of the document
        """
        ...

    @abstractmethod
    def write(self, document: FormattedDocument, path: Path) -> None:
        """Write formatted document to file.

        Args:
            document: The FormattedDocument with styled text
            path: Path to write the output document
        """
        ...

    def extract_images(self, path: Path) -> list[ImageRef]:
        """Extract images from the document.

        Default implementation returns empty list.
        Override in handlers that support image extraction.

        Args:
            path: Path to the input document

        Returns:
            List of ImageRef objects
        """
        return []

    def read_with_images(self, path: Path) -> tuple[str, list[ImageRef]]:
        """Read text and extract images in one pass.

        Args:
            path: Path to the input document

        Returns:
            Tuple of (text_content, list_of_images)
        """
        text = self.read(path)
        images = self.extract_images(path)
        return text, images
