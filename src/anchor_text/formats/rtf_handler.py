"""Rich Text Format (.rtf) file handler."""

from pathlib import Path

from striprtf.striprtf import rtf_to_text

from anchor_text.formats.base import FormatHandler
from anchor_text.formatting.ir import FormattedDocument


class RTFHandler(FormatHandler):
    """Handler for Rich Text Format (.rtf) files.

    Uses striprtf for reading RTF files.
    Writing creates a basic RTF with formatting.
    """

    @property
    def supported_extensions(self) -> tuple[str, ...]:
        return (".rtf",)

    def read(self, path: Path) -> str:
        """Extract plain text from RTF file."""
        rtf_content = path.read_text(encoding="utf-8", errors="ignore")
        return rtf_to_text(rtf_content)

    def write(self, document: FormattedDocument, path: Path) -> None:
        """Write formatted document to RTF file.

        Creates RTF with basic bold and italic formatting.
        """
        # RTF header
        rtf_parts: list[str] = [
            r"{\rtf1\ansi\deff0",
            r"{\fonttbl{\f0 Calibri;}}",
            r"{\colortbl;\red0\green0\blue0;}",
            r"\f0\fs24",  # Default font size 12pt (fs24 = 24 half-points)
        ]

        for block in document.blocks:
            # Start paragraph
            rtf_parts.append(r"\par ")

            for run in block.runs:
                # Escape special RTF characters
                text = (
                    run.text.replace("\\", "\\\\")
                    .replace("{", "\\{")
                    .replace("}", "\\}")
                )

                # Handle Unicode characters (like middle dot)
                escaped_text = ""
                for char in text:
                    if ord(char) > 127:
                        # RTF Unicode: \uN? where N is decimal code point
                        escaped_text += f"\\u{ord(char)}?"
                    else:
                        escaped_text += char
                text = escaped_text

                # Apply formatting
                if run.bold and run.italic:
                    rtf_parts.append(f"\\b\\i {text}\\b0\\i0 ")
                elif run.bold:
                    rtf_parts.append(f"\\b {text}\\b0 ")
                elif run.italic:
                    rtf_parts.append(f"\\i {text}\\i0 ")
                else:
                    rtf_parts.append(text)

        # Close RTF
        rtf_parts.append("}")

        content = "".join(rtf_parts)
        path.write_text(content, encoding="utf-8")
