"""EPUB e-book file handler."""

from pathlib import Path
import re
from typing import Optional

from ebooklib import epub
from bs4 import BeautifulSoup

from anchor_text.formats.base import FormatHandler
from anchor_text.formatting.ir import (
    FormattedDocument,
    ImageRef,
    TextBlock,
    VocabularyMetadata,
    LexicalMap,
    WordEntry,
    MorphemeFamily,
    DecoderTrap,
    TrapOption,
)


class EPUBHandler(FormatHandler):
    """Handler for EPUB e-book files.

    Uses ebooklib for reading and writing with support for
    bold and italic text formatting via HTML/CSS.
    """

    @property
    def supported_extensions(self) -> tuple[str, ...]:
        return (".epub",)

    def read(self, path: Path) -> str:
        """Extract plain text from EPUB file."""
        book = epub.read_epub(path)
        text_parts: list[str] = []

        for item in book.get_items():
            if item.get_type() == epub.ITEM_DOCUMENT:
                # Parse HTML content
                soup = BeautifulSoup(item.get_content(), "html.parser")

                # Remove script and style elements
                for element in soup(["script", "style"]):
                    element.decompose()

                # Get text
                text = soup.get_text(separator="\n")

                # Clean up whitespace
                lines = [line.strip() for line in text.split("\n")]
                text = "\n".join(line for line in lines if line)

                if text:
                    text_parts.append(text)

        return "\n\n".join(text_parts)

    def write(self, document: FormattedDocument, path: Path) -> None:
        """Write formatted document to EPUB file.

        Creates a new EPUB with proper formatting for e-readers.
        """
        book = epub.EpubBook()

        # Set metadata
        book.set_identifier("anchor-text-output")
        book.set_title(
            document.metadata.get("title", "Transformed Document")
        )
        book.set_language("en")

        # Add CSS for formatting
        style = """
        body {
            font-family: Georgia, serif;
            font-size: 1em;
            line-height: 1.6;
            margin: 1em;
        }
        p {
            margin: 0.5em 0;
        }
        /* Decoder trap styling */
        .decoder-trap {
            margin: 1.5em 0;
            padding: 1em;
            background: #E3F2FD;
            border-radius: 8px;
            border-left: 4px solid #1976D2;
        }
        .decoder-trap summary {
            font-weight: bold;
            cursor: pointer;
            color: #1976D2;
            padding: 0.5em 0;
        }
        .decoder-trap summary:hover {
            color: #1565C0;
        }
        .trap-options {
            list-style: none;
            padding: 0;
            margin: 1em 0;
        }
        .trap-options li {
            padding: 0.5em 1em;
            margin: 0.5em 0;
            background: #fff;
            border-radius: 4px;
            border: 1px solid #ddd;
        }
        .trap-options li:hover {
            background: #f5f5f5;
        }
        .answer-reveal {
            margin-top: 1em;
            padding: 1em;
            background: #E8F5E9;
            border-radius: 4px;
        }
        .answer-reveal summary {
            color: #2E7D32;
            font-weight: normal;
        }
        .correct-answer {
            font-weight: bold;
            color: #2E7D32;
        }
        /* Vocabulary section styling */
        .vocab-section {
            margin: 2em 0;
            padding: 1em;
            background: #FFF8E1;
            border-radius: 8px;
        }
        .vocab-header {
            font-size: 1.2em;
            font-weight: bold;
            color: #F57C00;
            margin-bottom: 1em;
        }
        .vocab-tier {
            margin: 1em 0;
        }
        .vocab-tier h4 {
            font-size: 1em;
            margin: 0.5em 0;
        }
        .tier-easy { background: #E8F5E9; padding: 0.5em; border-radius: 4px; }
        .tier-medium { background: #FFF3E0; padding: 0.5em; border-radius: 4px; }
        .tier-challenging { background: #FFEBEE; padding: 0.5em; border-radius: 4px; }
        .word-entry {
            margin: 0.5em 0;
            padding: 0.5em;
        }
        .word-syllables {
            font-weight: bold;
        }
        .word-morphemes {
            font-style: italic;
            color: #666;
        }
        /* Word families styling */
        .word-families {
            margin: 2em 0;
            padding: 1em;
            background: #F3E5F5;
            border-radius: 8px;
        }
        .family-root {
            font-weight: bold;
            color: #7B1FA2;
            margin: 0.5em 0;
        }
        .family-words {
            padding-left: 1em;
        }
        """

        css = epub.EpubItem(
            uid="style",
            file_name="style/main.css",
            media_type="text/css",
            content=style.encode("utf-8"),
        )
        book.add_item(css)

        # Create content chapter
        content_html = self._document_to_html(document)

        chapter = epub.EpubHtml(
            title="Content",
            file_name="content.xhtml",
            lang="en",
        )
        # Set content as bytes with UTF-8 encoding to handle emojis
        chapter.set_content(content_html.encode("utf-8"))
        chapter.add_item(css)
        book.add_item(chapter)

        # Add images
        for i, image in enumerate(document.images):
            img_item = epub.EpubImage()
            img_item.file_name = f"images/image_{i}.{image.format}"
            img_item.media_type = f"image/{image.format}"
            img_item.content = image.data
            book.add_item(img_item)

        # Set spine and TOC
        book.spine = ["nav", chapter]
        book.toc = [epub.Link("content.xhtml", "Content", "content")]

        # Add navigation
        book.add_item(epub.EpubNcx())
        book.add_item(epub.EpubNav())

        # Write the book
        epub.write_epub(path, book)

    def _document_to_html(self, document: FormattedDocument) -> str:
        """Convert FormattedDocument to HTML content."""
        html_parts: list[str] = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<!DOCTYPE html>',
            '<html xmlns="http://www.w3.org/1999/xhtml">',
            "<head>",
            '<meta charset="UTF-8"/>',
            "<title>Content</title>",
            '<link rel="stylesheet" type="text/css" href="style/main.css"/>',
            "</head>",
            "<body>",
        ]

        # Add vocabulary preview section if available
        if document.vocabulary and document.vocabulary.lexical_map:
            html_parts.append(self._render_vocabulary_section_html(
                document.vocabulary.lexical_map
            ))
            html_parts.append("<hr/>")

        for block in document.blocks:
            if block.is_decoder_trap:
                # Render as interactive collapsible section
                html_parts.append(self._render_trap_block_html(block))
            else:
                html_parts.append("<p>")
                for run in block.runs:
                    # Escape HTML
                    text = (
                        run.text.replace("&", "&amp;")
                        .replace("<", "&lt;")
                        .replace(">", "&gt;")
                    )

                    if run.bold and run.italic:
                        html_parts.append(f"<strong><em>{text}</em></strong>")
                    elif run.bold:
                        html_parts.append(f"<strong>{text}</strong>")
                    elif run.italic:
                        html_parts.append(f"<em>{text}</em>")
                    else:
                        html_parts.append(text)
                html_parts.append("</p>")

        # Add word families section at the end
        if document.vocabulary and document.vocabulary.lexical_map:
            families = document.vocabulary.lexical_map.get_root_families()
            if families:
                html_parts.append("<hr/>")
                html_parts.append(self._render_word_families_html(families))

        html_parts.extend(["</body>", "</html>"])

        return "\n".join(html_parts)

    def _render_trap_block_html(self, block: TextBlock) -> str:
        """Render a decoder trap block as interactive HTML."""
        # Extract the question text from the block
        question_text = block.plain_text

        # Parse the decoder check format: [Decoder Check: question]
        match = re.search(r'\[Decoder Check:\s*(.+?)\]', question_text)
        if match:
            question = match.group(1)
        else:
            question = question_text

        # Escape for HTML
        question = (
            question.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )

        # Create interactive HTML using <details> element
        html = f'''<div class="decoder-trap">
  <details>
    <summary>🔍 Decoder Check</summary>
    <p><strong>{question}</strong></p>
    <details class="answer-reveal">
      <summary>Tap to check your answer</summary>
      <p class="correct-answer">Think about the word carefully. Look for syllable patterns and morphemes you recognize.</p>
    </details>
  </details>
</div>'''
        return html

    def _render_vocabulary_section_html(self, lexical_map: LexicalMap) -> str:
        """Render vocabulary preview as HTML."""
        html_parts = [
            '<div class="vocab-section">',
            '<div class="vocab-header">📚 Vocabulary Preview</div>',
        ]

        # Render each difficulty tier
        for tier_name, tier_label, css_class in [
            ("challenging", "Challenging Words", "tier-challenging"),
            ("medium", "Medium Words", "tier-medium"),
            ("easy", "Familiar Words", "tier-easy"),
        ]:
            tier_words = lexical_map.difficulty_tiers.get(tier_name, [])
            if not tier_words:
                continue

            html_parts.append(f'<div class="vocab-tier {css_class}">')
            html_parts.append(f'<h4>{tier_label} ({len(tier_words)})</h4>')

            # Show up to 8 words per tier
            for word_key in tier_words[:8]:
                entry = lexical_map.words.get(word_key)
                if entry:
                    syllable_text = self._escape_html(entry.syllable_text)
                    morpheme_text = self._format_morphemes_html(entry)
                    html_parts.append(
                        f'<div class="word-entry">'
                        f'<span class="word-syllables">{syllable_text}</span>'
                    )
                    if morpheme_text:
                        html_parts.append(
                            f' <span class="word-morphemes">{morpheme_text}</span>'
                        )
                    html_parts.append('</div>')

            if len(tier_words) > 8:
                html_parts.append(
                    f'<p><em>... and {len(tier_words) - 8} more</em></p>'
                )

            html_parts.append('</div>')

        html_parts.append('</div>')
        return "\n".join(html_parts)

    def _render_word_families_html(self, families: list[MorphemeFamily]) -> str:
        """Render word families as HTML."""
        html_parts = [
            '<div class="word-families">',
            '<div class="vocab-header">🌳 Word Families</div>',
            '<p><em>Words grouped by their root morpheme</em></p>',
        ]

        for family in families[:6]:  # Show up to 6 families
            root = family.root
            root_text = self._escape_html(root.text.upper())
            if root.meaning:
                root_text += f" ({self._escape_html(root.meaning)})"
            if root.origin:
                root_text += f" - {self._escape_html(root.origin)}"

            html_parts.append(f'<div class="family-root">{root_text}</div>')
            html_parts.append('<div class="family-words">')

            word_list = ", ".join(
                f"<strong>{self._escape_html(w.syllable_text)}</strong>"
                for w in family.words[:5]
            )
            if len(family.words) > 5:
                word_list += f", ... (+{len(family.words) - 5} more)"

            html_parts.append(f'<p>{word_list}</p>')
            html_parts.append('</div>')

        html_parts.append('</div>')
        return "\n".join(html_parts)

    def _format_morphemes_html(self, entry: WordEntry) -> str:
        """Format morpheme breakdown for HTML display."""
        if not entry.morphemes:
            return ""
        parts = []
        for m in entry.morphemes:
            text = self._escape_html(m.text)
            if m.meaning:
                meaning = self._escape_html(m.meaning)
                parts.append(f"{text} ({meaning})")
            else:
                parts.append(text)
        return " + ".join(parts)

    def _escape_html(self, text: str) -> str:
        """Escape HTML special characters."""
        return (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )

    def extract_images(self, path: Path) -> list[ImageRef]:
        """Extract images from EPUB file."""
        book = epub.read_epub(path)
        images: list[ImageRef] = []

        for item in book.get_items():
            if item.get_type() == epub.ITEM_IMAGE:
                # Determine format from media type
                media_type = item.media_type
                if "png" in media_type:
                    fmt = "png"
                elif "jpeg" in media_type or "jpg" in media_type:
                    fmt = "jpg"
                elif "gif" in media_type:
                    fmt = "gif"
                else:
                    fmt = "png"  # Default

                images.append(
                    ImageRef(
                        data=item.get_content(),
                        format=fmt,
                        position=len(images),
                    )
                )

        return images
