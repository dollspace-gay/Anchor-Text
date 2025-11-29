"""Tests for TXT handler."""

import pytest
from pathlib import Path

from anchor_text.formats.txt_handler import TXTHandler
from anchor_text.formatting.ir import (
    FormattedDocument,
    TextBlock,
    TextRun,
    TextStyle,
)


class TestTXTHandler:
    """Tests for the TXT format handler."""

    def test_supported_extensions(self):
        """Test that handler supports .txt extension."""
        handler = TXTHandler()
        assert ".txt" in handler.supported_extensions

    def test_read_plain_text(self, tmp_path: Path):
        """Test reading plain text file."""
        file_path = tmp_path / "test.txt"
        file_path.write_text("Hello, world!", encoding="utf-8")

        handler = TXTHandler()
        text = handler.read(file_path)

        assert text == "Hello, world!"

    def test_read_multiline(self, tmp_path: Path):
        """Test reading multiline text file."""
        content = "Line one.\n\nLine two.\n\nLine three."
        file_path = tmp_path / "test.txt"
        file_path.write_text(content, encoding="utf-8")

        handler = TXTHandler()
        text = handler.read(file_path)

        assert text == content

    def test_write_plain_text(self, tmp_path: Path):
        """Test writing plain text without formatting."""
        doc = FormattedDocument(
            blocks=[
                TextBlock(runs=[TextRun(text="Hello, world!")])
            ]
        )

        output_path = tmp_path / "output.txt"
        handler = TXTHandler()
        handler.write(doc, output_path)

        assert output_path.read_text(encoding="utf-8") == "Hello, world!"

    def test_write_bold_text(self, tmp_path: Path):
        """Test writing bold text with markdown."""
        doc = FormattedDocument(
            blocks=[
                TextBlock(runs=[
                    TextRun(text="Hello "),
                    TextRun(text="world", style=TextStyle.BOLD),
                    TextRun(text="!"),
                ])
            ]
        )

        output_path = tmp_path / "output.txt"
        handler = TXTHandler()
        handler.write(doc, output_path)

        assert output_path.read_text(encoding="utf-8") == "Hello **world**!"

    def test_write_italic_text(self, tmp_path: Path):
        """Test writing italic text with markdown."""
        doc = FormattedDocument(
            blocks=[
                TextBlock(runs=[
                    TextRun(text="She "),
                    TextRun(text="ran", style=TextStyle.ITALIC),
                    TextRun(text=" quickly."),
                ])
            ]
        )

        output_path = tmp_path / "output.txt"
        handler = TXTHandler()
        handler.write(doc, output_path)

        assert output_path.read_text(encoding="utf-8") == "She *ran* quickly."

    def test_write_bold_italic_text(self, tmp_path: Path):
        """Test writing bold+italic text."""
        doc = FormattedDocument(
            blocks=[
                TextBlock(runs=[
                    TextRun(text="Very "),
                    TextRun(
                        text="important",
                        style=TextStyle.BOLD | TextStyle.ITALIC,
                    ),
                    TextRun(text=" word."),
                ])
            ]
        )

        output_path = tmp_path / "output.txt"
        handler = TXTHandler()
        handler.write(doc, output_path)

        assert output_path.read_text(encoding="utf-8") == "Very ***important*** word."

    def test_write_multiple_blocks(self, tmp_path: Path):
        """Test writing multiple paragraphs."""
        doc = FormattedDocument(
            blocks=[
                TextBlock(runs=[TextRun(text="First paragraph.")]),
                TextBlock(runs=[TextRun(text="Second paragraph.")]),
            ]
        )

        output_path = tmp_path / "output.txt"
        handler = TXTHandler()
        handler.write(doc, output_path)

        content = output_path.read_text(encoding="utf-8")
        assert content == "First paragraph.\n\nSecond paragraph."

    def test_roundtrip_preserves_text(self, tmp_path: Path):
        """Test that read -> write -> read preserves content."""
        original = "The quick brown fox jumps."
        input_path = tmp_path / "input.txt"
        input_path.write_text(original, encoding="utf-8")

        handler = TXTHandler()
        text = handler.read(input_path)

        doc = FormattedDocument(
            blocks=[TextBlock(runs=[TextRun(text=text)])]
        )

        output_path = tmp_path / "output.txt"
        handler.write(doc, output_path)

        result = handler.read(output_path)
        assert result == original
