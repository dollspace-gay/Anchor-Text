"""PDF file handler."""

import io
from pathlib import Path
from typing import Optional

import pdfplumber
from PIL import Image
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Image as RLImage,
)

from anchor_text.formats.base import FormatHandler
from anchor_text.formatting.ir import FormattedDocument, ImageRef, TextBlock


class PDFHandler(FormatHandler):
    """Handler for PDF files.

    Uses pdfplumber for reading (with image extraction) and
    reportlab for writing with rich text formatting.

    Note: PDF writing creates a fresh layout - original formatting
    is intentionally not preserved as the goal is to reformat
    for phonics learning.
    """

    @property
    def supported_extensions(self) -> tuple[str, ...]:
        return (".pdf",)

    def read(self, path: Path) -> str:
        """Extract plain text from PDF file."""
        text_parts: list[str] = []

        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    text_parts.append(text.strip())

        return "\n\n".join(text_parts)

    def write(self, document: FormattedDocument, path: Path) -> None:
        """Write formatted document to PDF file.

        Creates a fresh PDF with proper typography for reading.
        Uses reportlab's Paragraph with HTML-like tags for formatting.
        """
        doc = SimpleDocTemplate(
            str(path),
            pagesize=letter,
            rightMargin=inch,
            leftMargin=inch,
            topMargin=inch,
            bottomMargin=inch,
        )

        # Create styles
        styles = getSampleStyleSheet()
        body_style = ParagraphStyle(
            "BodyText",
            parent=styles["Normal"],
            fontSize=12,
            leading=18,  # Line spacing
            spaceBefore=6,
            spaceAfter=6,
        )
        decoder_style = ParagraphStyle(
            "DecoderTrap",
            parent=styles["Normal"],
            fontSize=11,
            leading=16,
            spaceBefore=20,
            spaceAfter=6,
            fontName="Helvetica-Oblique",
        )

        story: list = []
        image_index = 0

        for block in document.blocks:
            # Check if we should insert an image before this block
            while (
                image_index < len(document.images)
                and document.images[image_index].position <= len(story)
            ):
                img = document.images[image_index]
                story.append(self._create_image_flowable(img))
                story.append(Spacer(1, 12))
                image_index += 1

            # Convert block to reportlab Paragraph with HTML formatting
            html_text = self._block_to_html(block)
            style = decoder_style if block.is_decoder_trap else body_style
            story.append(Paragraph(html_text, style))

        # Add any remaining images at the end
        while image_index < len(document.images):
            img = document.images[image_index]
            story.append(Spacer(1, 12))
            story.append(self._create_image_flowable(img))
            image_index += 1

        doc.build(story)

    def _block_to_html(self, block: TextBlock) -> str:
        """Convert a TextBlock to HTML-formatted string for reportlab."""
        parts: list[str] = []

        for run in block.runs:
            # Escape HTML special characters
            text = (
                run.text.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
            )

            if run.bold and run.italic:
                text = f"<b><i>{text}</i></b>"
            elif run.bold:
                text = f"<b>{text}</b>"
            elif run.italic:
                text = f"<i>{text}</i>"

            parts.append(text)

        return "".join(parts)

    def _create_image_flowable(
        self, image: ImageRef, max_width: float = 5 * inch
    ) -> RLImage:
        """Create a reportlab Image flowable from ImageRef."""
        # Load image to get dimensions
        img_data = io.BytesIO(image.data)
        pil_img = Image.open(img_data)
        width, height = pil_img.size

        # Scale to fit within max_width while maintaining aspect ratio
        if width > max_width:
            scale = max_width / width
            width = max_width
            height = height * scale

        # Create reportlab image
        img_data.seek(0)
        return RLImage(img_data, width=width, height=height)

    def extract_images(self, path: Path) -> list[ImageRef]:
        """Extract images from PDF file."""
        images: list[ImageRef] = []

        with pdfplumber.open(path) as pdf:
            for page_num, page in enumerate(pdf.pages):
                if hasattr(page, "images") and page.images:
                    for img_info in page.images:
                        try:
                            # Extract image using pdfplumber
                            img = page.within_bbox(
                                (
                                    img_info["x0"],
                                    img_info["top"],
                                    img_info["x1"],
                                    img_info["bottom"],
                                )
                            ).to_image()

                            # Convert to bytes
                            img_bytes = io.BytesIO()
                            img.original.save(img_bytes, format="PNG")

                            images.append(
                                ImageRef(
                                    data=img_bytes.getvalue(),
                                    format="png",
                                    width=int(img_info["x1"] - img_info["x0"]),
                                    height=int(
                                        img_info["bottom"] - img_info["top"]
                                    ),
                                    page=page_num,
                                    position=len(images),
                                )
                            )
                        except Exception:
                            # Skip images that can't be extracted
                            pass

        return images
