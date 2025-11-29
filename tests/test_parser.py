"""Tests for the markdown parser."""

import pytest

from anchor_text.formatting.parser import MarkdownParser
from anchor_text.formatting.ir import TextStyle


class TestMarkdownParser:
    """Tests for the MarkdownParser class."""

    @pytest.fixture
    def parser(self) -> MarkdownParser:
        """Create a parser instance."""
        return MarkdownParser()

    def test_parse_plain_text(self, parser: MarkdownParser):
        """Test parsing plain text without formatting."""
        doc = parser.parse("Hello, world!")

        assert len(doc.blocks) == 1
        assert len(doc.blocks[0].runs) == 1
        assert doc.blocks[0].runs[0].text == "Hello, world!"
        assert doc.blocks[0].runs[0].style == TextStyle.NONE

    def test_parse_bold_text(self, parser: MarkdownParser):
        """Test parsing bold text."""
        doc = parser.parse("This is **bold** text")

        assert len(doc.blocks) == 1
        runs = doc.blocks[0].runs

        assert runs[0].text == "This is "
        assert runs[0].bold is False

        assert runs[1].text == "bold"
        assert runs[1].bold is True

        assert runs[2].text == " text"
        assert runs[2].bold is False

    def test_parse_italic_text(self, parser: MarkdownParser):
        """Test parsing italic text."""
        doc = parser.parse("She *ran* quickly")

        assert len(doc.blocks) == 1
        runs = doc.blocks[0].runs

        assert runs[0].text == "She "
        assert runs[0].italic is False

        assert runs[1].text == "ran"
        assert runs[1].italic is True

        assert runs[2].text == " quickly"
        assert runs[2].italic is False

    def test_parse_bold_italic_text(self, parser: MarkdownParser):
        """Test parsing bold+italic text."""
        doc = parser.parse("This is ***important*** stuff")

        assert len(doc.blocks) == 1
        runs = doc.blocks[0].runs

        assert runs[1].text == "important"
        assert runs[1].bold is True
        assert runs[1].italic is True

    def test_parse_multiple_paragraphs(self, parser: MarkdownParser):
        """Test parsing multiple paragraphs."""
        text = "First paragraph.\n\nSecond paragraph."
        doc = parser.parse(text)

        assert len(doc.blocks) == 2
        assert doc.blocks[0].plain_text == "First paragraph."
        assert doc.blocks[1].plain_text == "Second paragraph."

    def test_parse_middle_dot_preserved(self, parser: MarkdownParser):
        """Test that middle dots (·) are preserved."""
        doc = parser.parse("phi·los·o·phy")

        assert len(doc.blocks) == 1
        assert "·" in doc.blocks[0].plain_text
        assert doc.blocks[0].plain_text == "phi·los·o·phy"

    def test_parse_decoder_trap_detected(self, parser: MarkdownParser):
        """Test that Decoder's Trap is detected."""
        text = "Some text.\n\n[Decoder Check: What word means happy?]"
        doc = parser.parse(text)

        assert len(doc.blocks) == 2
        assert doc.blocks[0].is_decoder_trap is False
        assert doc.blocks[1].is_decoder_trap is True

    def test_parse_decoder_trap_alternative_format(self, parser: MarkdownParser):
        """Test Decoder's Trap with alternative format."""
        text = "Some text.\n\nDECODER'S TRAP: What is the answer?"
        doc = parser.parse(text)

        assert doc.blocks[1].is_decoder_trap is True

    def test_parse_complex_formatting(self, parser: MarkdownParser):
        """Test parsing complex mixed formatting."""
        text = "**The cat** *sat* on **the** mat."
        doc = parser.parse(text)

        runs = doc.blocks[0].runs
        texts = [r.text for r in runs]

        assert "The cat" in texts
        assert "sat" in texts
        assert "the" in texts

        # Check formatting
        for run in runs:
            if run.text == "The cat":
                assert run.bold is True
            elif run.text == "sat":
                assert run.italic is True
            elif run.text == "the":
                assert run.bold is True

    def test_has_decoder_trap_property(self, parser: MarkdownParser):
        """Test the has_decoder_trap document property."""
        text_with_trap = "Text.\n\n[Decoder Check: Question?]"
        text_without = "Just some text."

        doc_with = parser.parse(text_with_trap)
        doc_without = parser.parse(text_without)

        assert doc_with.has_decoder_trap is True
        assert doc_without.has_decoder_trap is False

    def test_to_markdown_roundtrip(self, parser: MarkdownParser):
        """Test converting document back to markdown."""
        original = "**Bold** and *italic* text."
        doc = parser.parse(original)
        markdown = parser.to_markdown(doc)

        # Parse again and compare
        doc2 = parser.parse(markdown)

        assert doc.plain_text == doc2.plain_text

    def test_to_plain_text(self, parser: MarkdownParser):
        """Test converting document to plain text."""
        text = "**Bold** and *italic* text."
        doc = parser.parse(text)
        plain = parser.to_plain_text(doc)

        assert plain == "Bold and italic text."
