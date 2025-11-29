"""OpenDocument Text (.odt) file handler."""

from pathlib import Path
import zipfile
from io import BytesIO

from odf.opendocument import OpenDocumentText, load
from odf.style import Style, TextProperties
from odf.text import P, Span
from odf import text as odf_text

from anchor_text.formats.base import FormatHandler
from anchor_text.formatting.ir import FormattedDocument, ImageRef


class ODTHandler(FormatHandler):
    """Handler for OpenDocument Text (.odt) files.

    Uses odfpy for reading and writing with support for
    bold and italic text formatting via styles.
    """

    @property
    def supported_extensions(self) -> tuple[str, ...]:
        return (".odt",)

    def read(self, path: Path) -> str:
        """Extract plain text from ODT file."""
        doc = load(path)
        paragraphs: list[str] = []

        for para in doc.getElementsByType(odf_text.P):
            # Get all text content from paragraph and children
            text = self._extract_text_from_element(para)
            if text.strip():
                paragraphs.append(text.strip())

        return "\n\n".join(paragraphs)

    def _extract_text_from_element(self, element) -> str:
        """Recursively extract text from an ODF element."""
        text_parts: list[str] = []

        for node in element.childNodes:
            if node.nodeType == node.TEXT_NODE:
                text_parts.append(str(node))
            elif hasattr(node, "childNodes"):
                text_parts.append(self._extract_text_from_element(node))

        return "".join(text_parts)

    def write(self, document: FormattedDocument, path: Path) -> None:
        """Write formatted document to ODT file.

        Creates a new ODT document with automatic styles for
        bold and italic text.
        """
        doc = OpenDocumentText()

        # Create text styles
        bold_style = Style(name="Bold", family="text")
        bold_style.addElement(TextProperties(fontweight="bold"))
        doc.automaticstyles.addElement(bold_style)

        italic_style = Style(name="Italic", family="text")
        italic_style.addElement(TextProperties(fontstyle="italic"))
        doc.automaticstyles.addElement(italic_style)

        bold_italic_style = Style(name="BoldItalic", family="text")
        bold_italic_style.addElement(
            TextProperties(fontweight="bold", fontstyle="italic")
        )
        doc.automaticstyles.addElement(bold_italic_style)

        for block in document.blocks:
            para = P()

            for run in block.runs:
                if run.bold and run.italic:
                    span = Span(stylename=bold_italic_style)
                    span.addText(run.text)
                    para.addElement(span)
                elif run.bold:
                    span = Span(stylename=bold_style)
                    span.addText(run.text)
                    para.addElement(span)
                elif run.italic:
                    span = Span(stylename=italic_style)
                    span.addText(run.text)
                    para.addElement(span)
                else:
                    # Plain text - add directly or in unstyled span
                    para.addText(run.text)

            doc.text.addElement(para)

        doc.save(path)

    def extract_images(self, path: Path) -> list[ImageRef]:
        """Extract images from ODT file."""
        images: list[ImageRef] = []

        # ODT is a ZIP file - extract images from Pictures folder
        with zipfile.ZipFile(path, "r") as zf:
            for name in zf.namelist():
                if name.startswith("Pictures/"):
                    data = zf.read(name)
                    ext = Path(name).suffix.lower().lstrip(".")
                    if ext in ("png", "jpg", "jpeg", "gif", "bmp"):
                        if ext == "jpeg":
                            ext = "jpg"
                        images.append(
                            ImageRef(
                                data=data,
                                format=ext,
                                position=len(images),
                            )
                        )

        return images
