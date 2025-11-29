"""Plain text file handler."""

from pathlib import Path

from anchor_text.formats.base import FormatHandler
from anchor_text.formatting.ir import FormattedDocument, TextStyle


class TXTHandler(FormatHandler):
    """Handler for plain text (.txt) files.

    Plain text files support formatting via markdown-style syntax:
    - **bold** for bold text
    - *italic* for italic text
    - Middle dots (·) for syllable breaks
    """

    @property
    def supported_extensions(self) -> tuple[str, ...]:
        return (".txt",)

    def read(self, path: Path) -> str:
        """Read plain text from file."""
        return path.read_text(encoding="utf-8")

    def write(self, document: FormattedDocument, path: Path) -> None:
        """Write formatted document as markdown-styled plain text.

        The output preserves markdown formatting so it can be read
        in any text editor or rendered by markdown viewers.
        """
        lines: list[str] = []

        for block in document.blocks:
            line_parts: list[str] = []
            for run in block.runs:
                text = run.text

                # Apply markdown formatting
                if run.bold and run.italic:
                    text = f"***{text}***"
                elif run.bold:
                    text = f"**{text}**"
                elif run.italic:
                    text = f"*{text}*"

                line_parts.append(text)

            lines.append("".join(line_parts))

        # Join blocks with double newlines (paragraphs)
        content = "\n\n".join(lines)
        path.write_text(content, encoding="utf-8")
