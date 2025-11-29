"""Tests for LLM output validation."""

import pytest

from anchor_text.llm.client import validate_transformation


class TestValidateTransformation:
    """Tests for the validate_transformation function."""

    def test_valid_output_passes(self):
        """Test that a fully valid output passes validation."""
        output = """**The cat** *sat* on the mat.

**Phi·los·o·phy** *is* the study of **fun·da·men·tal** questions.

[Decoder Check: What word has four syllables?]"""

        is_valid, issues = validate_transformation(output)

        assert is_valid is True
        assert len(issues) == 0

    def test_missing_bold_fails(self):
        """Test that missing bold formatting is detected."""
        output = """The cat *sat* on the mat.

Phi·los·o·phy is the study of questions.

[Decoder Check: What word has four syllables?]"""

        is_valid, issues = validate_transformation(output)

        assert is_valid is False
        assert any("bold" in issue.lower() for issue in issues)

    def test_missing_italic_fails(self):
        """Test that missing italic formatting is detected."""
        output = """**The cat** sat on the mat.

**Phi·los·o·phy** is the study of **fun·da·men·tal** questions.

[Decoder Check: What word has four syllables?]"""

        is_valid, issues = validate_transformation(output)

        assert is_valid is False
        assert any("italic" in issue.lower() for issue in issues)

    def test_missing_middle_dots_fails(self):
        """Test that missing syllable breaks are detected."""
        output = """**The cat** *sat* on the mat.

**Philosophy** *is* the study of **fundamental** questions.

[Decoder Check: What word has four syllables?]"""

        is_valid, issues = validate_transformation(output)

        assert is_valid is False
        assert any("syllable" in issue.lower() or "dot" in issue.lower() for issue in issues)

    def test_missing_decoder_trap_fails(self):
        """Test that missing Decoder's Trap is detected."""
        output = """**The cat** *sat* on the mat.

**Phi·los·o·phy** *is* the study of **fun·da·men·tal** questions."""

        is_valid, issues = validate_transformation(output)

        assert is_valid is False
        assert any("decoder" in issue.lower() for issue in issues)

    def test_decoder_trap_not_required_when_disabled(self):
        """Test that Decoder's Trap can be optional."""
        output = """**The cat** *sat* on the mat.

**Phi·los·o·phy** *is* the study of **fun·da·men·tal** questions."""

        is_valid, issues = validate_transformation(output, expect_decoder_trap=False)

        assert is_valid is True

    def test_alternative_decoder_trap_formats(self):
        """Test that alternative Decoder's Trap formats are accepted."""
        formats = [
            "[Decoder Check: Question?]",
            "DECODER'S TRAP: Question?",
            "Decoder's Trap: Question?",
        ]

        for trap in formats:
            output = f"""**The cat** *sat* on the mat.

**Phi·los·o·phy** *is* the study.

{trap}"""

            is_valid, issues = validate_transformation(output)
            assert is_valid is True, f"Format not accepted: {trap}"

    def test_completely_invalid_output(self):
        """Test that completely plain text fails all checks."""
        output = "The cat sat on the mat. Philosophy is great."

        is_valid, issues = validate_transformation(output)

        assert is_valid is False
        assert len(issues) >= 3  # Should fail multiple checks
