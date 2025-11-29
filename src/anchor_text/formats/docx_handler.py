"""Microsoft Word (.docx) file handler."""

from pathlib import Path

from docx import Document
from docx.shared import Pt

from anchor_text.formats.base import FormatHandler
from anchor_text.formatting.ir import FormattedDocument, ImageRef


class DOCXHandler(FormatHandler):
    """Handler for Microsoft Word (.docx) files.

    Uses python-docx for reading and writing with full support for
    bold and italic text formatting at the run level.
    """

    @property
    def supported_extensions(self) -> tuple[str, ...]:
        return (".docx",)

    def read(self, path: Path) -> str:
        """Extract plain text from DOCX file."""
        doc = Document(path)
        paragraphs: list[str] = []

        for para in doc.paragraphs:
            text = para.text.strip()
            if text:
                paragraphs.append(text)

        return "\n\n".join(paragraphs)

    def write(self, document: FormattedDocument, path: Path) -> None:
        """Write formatted document to DOCX file.

        Creates a new Word document with run-level formatting for
        bold and italic text.
        """
        doc = Document()

        # Set default font
        style = doc.styles["Normal"]
        font = style.font
        font.name = "Calibri"
        font.size = Pt(11)

        for block in document.blocks:
            para = doc.add_paragraph()

            for run_data in block.runs:
                run = para.add_run(run_data.text)
                run.bold = run_data.bold
                run.italic = run_data.italic

        # Insert images at their positions
        # Note: This is simplified - images go at the end
        # More sophisticated positioning would require tracking
        # exact positions during text extraction
        for image in document.images:
            doc.add_paragraph()  # Add spacing
            para = doc.add_paragraph()
            run = para.add_run()

            # Save image to temp file and add to document
            import tempfile
            import os

            with tempfile.NamedTemporaryFile(
                suffix=f".{image.format}", delete=False
            ) as f:
                f.write(image.data)
                temp_path = f.name

            try:
                run.add_picture(temp_path)
            finally:
                os.unlink(temp_path)

        doc.save(path)

    def extract_images(self, path: Path) -> list[ImageRef]:
        """Extract images from DOCX file."""
        from docx import Document
        import zipfile
        from io import BytesIO

        images: list[ImageRef] = []
        position = 0

        # DOCX is a ZIP file - extract images from media folder
        with zipfile.ZipFile(path, "r") as zf:
            for name in zf.namelist():
                if name.startswith("word/media/"):
                    data = zf.read(name)
                    # Determine format from filename
                    ext = Path(name).suffix.lower().lstrip(".")
                    if ext in ("png", "jpg", "jpeg", "gif", "bmp"):
                        if ext == "jpeg":
                            ext = "jpg"
                        images.append(
                            ImageRef(
                                data=data,
                                format=ext,
                                position=position,
                            )
                        )
                        position += 1

        return images
