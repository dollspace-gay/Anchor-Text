"""EPUB e-book file handler."""

from pathlib import Path
import re
from typing import Optional

from ebooklib import epub
from bs4 import BeautifulSoup

from anchor_text.formats.base import FormatHandler
from anchor_text.formatting.ir import FormattedDocument, ImageRef


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
        .decoder-trap {
            font-style: italic;
            margin-top: 2em;
            padding: 1em;
            background: #f5f5f5;
            border-left: 3px solid #666;
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
        chapter.set_content(content_html)
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

        for block in document.blocks:
            css_class = ' class="decoder-trap"' if block.is_decoder_trap else ""
            html_parts.append(f"<p{css_class}>")

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

        html_parts.extend(["</body>", "</html>"])

        return "\n".join(html_parts)

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
