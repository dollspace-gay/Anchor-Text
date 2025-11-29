"""PDF file handler."""

import io
from pathlib import Path

import pdfplumber
from PIL import Image
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Image as RLImage,
    Table,
    TableStyle,
    HRFlowable,
)

from anchor_text.formats.base import FormatHandler
from anchor_text.formatting.ir import (
    FormattedDocument,
    ImageRef,
    TextBlock,
    VocabularyMetadata,
    WordEntry,
    MorphemeFamily,
)


# Color definitions for vocabulary tiers
DIFFICULTY_COLORS = {
    "easy": HexColor("#E8F5E9"),      # Light green
    "medium": HexColor("#FFF3E0"),    # Light orange
    "challenging": HexColor("#FFEBEE"),  # Light red
}
TRAP_BG_COLOR = HexColor("#E3F2FD")  # Light blue
VOCAB_HEADER_COLOR = HexColor("#1976D2")  # Blue


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
        Includes vocabulary sidebar and styled decoder traps when available.
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
        styles = self._create_styles()

        story: list = []
        image_index = 0

        # Add vocabulary section at the beginning if available
        separator_color = HexColor("#CCCCCC")
        if document.vocabulary and document.vocabulary.lexical_map:
            story.extend(self._render_vocabulary_section(
                document.vocabulary, styles
            ))
            story.append(Spacer(1, 24))
            story.append(HRFlowable(width="100%", thickness=1, color=separator_color))
            story.append(Spacer(1, 24))

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
            if block.is_decoder_trap:
                # Render decoder trap with styled box
                story.extend(self._render_trap_block(block, styles))
            else:
                html_text = self._block_to_html(block)
                story.append(Paragraph(html_text, styles["body"]))

        # Add any remaining images at the end
        while image_index < len(document.images):
            img = document.images[image_index]
            story.append(Spacer(1, 12))
            story.append(self._create_image_flowable(img))
            image_index += 1

        # Add vocabulary appendix (word families) at the end
        if document.vocabulary and document.vocabulary.lexical_map:
            families = document.vocabulary.lexical_map.get_root_families()
            if families:
                story.append(Spacer(1, 36))
                story.append(HRFlowable(
                    width="100%", thickness=1, color=separator_color
                ))
                story.append(Spacer(1, 24))
                story.extend(self._render_word_families(families, styles))

        doc.build(story)

    def _create_styles(self) -> dict[str, ParagraphStyle]:
        """Create all paragraph styles for the document."""
        base_styles = getSampleStyleSheet()
        return {
            "body": ParagraphStyle(
                "BodyText",
                parent=base_styles["Normal"],
                fontSize=12,
                leading=18,
                spaceBefore=6,
                spaceAfter=6,
            ),
            "trap": ParagraphStyle(
                "DecoderTrap",
                parent=base_styles["Normal"],
                fontSize=11,
                leading=16,
                spaceBefore=6,
                spaceAfter=6,
            ),
            "vocab_header": ParagraphStyle(
                "VocabHeader",
                parent=base_styles["Heading2"],
                fontSize=14,
                textColor=VOCAB_HEADER_COLOR,
                spaceBefore=12,
                spaceAfter=6,
            ),
            "vocab_subheader": ParagraphStyle(
                "VocabSubheader",
                parent=base_styles["Heading3"],
                fontSize=11,
                spaceBefore=10,
                spaceAfter=4,
            ),
            "vocab_word": ParagraphStyle(
                "VocabWord",
                parent=base_styles["Normal"],
                fontSize=10,
                leading=14,
            ),
            "family_header": ParagraphStyle(
                "FamilyHeader",
                parent=base_styles["Heading3"],
                fontSize=12,
                textColor=VOCAB_HEADER_COLOR,
                spaceBefore=12,
                spaceAfter=6,
            ),
        }

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

    def _render_vocabulary_section(
        self, vocab: VocabularyMetadata, styles: dict[str, ParagraphStyle]
    ) -> list:
        """Render vocabulary summary section at the beginning of the document."""
        elements: list = []

        # Header
        elements.append(Paragraph(
            "<b>VOCABULARY PREVIEW</b>",
            styles["vocab_header"]
        ))

        lexical_map = vocab.lexical_map
        if not lexical_map:
            return elements

        # Render difficulty tiers as colored tables
        for tier_name, tier_label in [
            ("challenging", "Challenging Words"),
            ("medium", "Medium Words"),
            ("easy", "Familiar Words"),
        ]:
            tier_words = lexical_map.difficulty_tiers.get(tier_name, [])
            if not tier_words:
                continue

            elements.append(Paragraph(
                f"<b>{tier_label}</b> ({len(tier_words)} words)",
                styles["vocab_subheader"]
            ))

            # Build table data - show up to 10 words per tier
            table_data = []
            display_words = tier_words[:10]
            for word_key in display_words:
                entry = lexical_map.words.get(word_key)
                if entry:
                    # Word with syllables | Morpheme breakdown
                    syllable_text = entry.syllable_text
                    morpheme_text = self._format_morphemes(entry)
                    table_data.append([
                        Paragraph(f"<b>{syllable_text}</b>", styles["vocab_word"]),
                        Paragraph(morpheme_text, styles["vocab_word"]),
                    ])

            if table_data:
                table = Table(table_data, colWidths=[2.5 * inch, 3.5 * inch])
                table.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (-1, -1), DIFFICULTY_COLORS[tier_name]),
                    ("GRID", (0, 0), (-1, -1), 0.5, HexColor("#CCCCCC")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]))
                elements.append(table)
                elements.append(Spacer(1, 8))

            if len(tier_words) > 10:
                elements.append(Paragraph(
                    f"<i>... and {len(tier_words) - 10} more {tier_name} words</i>",
                    styles["vocab_word"]
                ))

        return elements

    def _format_morphemes(self, entry: WordEntry) -> str:
        """Format morpheme breakdown for display."""
        if not entry.morphemes:
            return ""
        parts = []
        for m in entry.morphemes:
            if m.meaning:
                parts.append(f"{m.text} ({m.meaning})")
            else:
                parts.append(m.text)
        return " + ".join(parts)

    def _render_trap_block(
        self, block: TextBlock, styles: dict[str, ParagraphStyle]
    ) -> list:
        """Render a decoder trap block with styled box."""
        elements: list = []

        # Get the trap text
        html_text = self._block_to_html(block)

        # Create a table to act as a styled box
        trap_para = Paragraph(html_text, styles["trap"])
        table_data = [[trap_para]]
        table = Table(table_data, colWidths=[5.5 * inch])
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), TRAP_BG_COLOR),
            ("BOX", (0, 0), (-1, -1), 1.5, VOCAB_HEADER_COLOR),
            ("LEFTPADDING", (0, 0), (-1, -1), 12),
            ("RIGHTPADDING", (0, 0), (-1, -1), 12),
            ("TOPPADDING", (0, 0), (-1, -1), 10),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ]))

        elements.append(Spacer(1, 12))
        elements.append(table)
        elements.append(Spacer(1, 12))

        return elements

    def _render_word_families(
        self, families: list[MorphemeFamily], styles: dict[str, ParagraphStyle]
    ) -> list:
        """Render word families appendix section."""
        elements: list = []

        elements.append(Paragraph(
            "<b>WORD FAMILIES</b>",
            styles["vocab_header"]
        ))
        elements.append(Paragraph(
            "Words grouped by their root morpheme",
            styles["vocab_word"]
        ))
        elements.append(Spacer(1, 12))

        for family in families[:8]:  # Show up to 8 families
            root = family.root
            root_text = root.text.upper()
            if root.meaning:
                root_text += f" ({root.meaning})"
            if root.origin:
                root_text += f" - {root.origin}"

            elements.append(Paragraph(
                f"<b>{root_text}</b>",
                styles["family_header"]
            ))

            # List words in this family
            word_list = ", ".join(
                f"<b>{w.syllable_text}</b>" for w in family.words[:6]
            )
            if len(family.words) > 6:
                word_list += f", ... (+{len(family.words) - 6} more)"

            elements.append(Paragraph(word_list, styles["vocab_word"]))
            elements.append(Spacer(1, 6))

        return elements

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
