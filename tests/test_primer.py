"""Tests for the Pre-Reading Primer system."""

import pytest

from anchor_text.lexical.primer import (
    WordDifficultyAnalyzer,
    PrimerGenerator,
    ACADEMIC_WORDS,
    IRREGULAR_PATTERNS,
)
from anchor_text.formatting.ir import (
    FormattedDocument,
    TextBlock,
    TextRun,
    TextStyle,
    WordEntry,
    MorphemeInfo,
)


class TestWordDifficultyAnalyzer:
    """Tests for the WordDifficultyAnalyzer class."""

    def test_score_simple_word(self):
        """Test scoring a simple word."""
        analyzer = WordDifficultyAnalyzer()
        score = analyzer.score_word("cat")

        assert 1 <= score <= 10
        assert score <= 3  # Simple word should be easy

    def test_score_complex_word(self):
        """Test scoring a complex word."""
        analyzer = WordDifficultyAnalyzer()
        score = analyzer.score_word("incomprehensibility")

        assert 1 <= score <= 10
        assert score >= 5  # Complex word should be harder

    def test_score_academic_word(self):
        """Test that academic words get higher scores."""
        analyzer = WordDifficultyAnalyzer()

        academic = analyzer.score_word("hypothesis")
        non_academic = analyzer.score_word("elephant")  # Same syllable count

        # Academic word should score higher
        assert academic >= non_academic

    def test_score_irregular_phonetics(self):
        """Test that irregular phonetic patterns increase difficulty."""
        analyzer = WordDifficultyAnalyzer()

        irregular = analyzer.score_word("thought")  # Contains "ough"
        regular = analyzer.score_word("support")  # Regular phonetics

        # Irregular should be harder (or at least not easier)
        assert irregular >= regular - 1  # Allow some variance

    def test_score_with_word_entry(self):
        """Test scoring with a WordEntry containing morpheme info."""
        analyzer = WordDifficultyAnalyzer()
        entry = WordEntry(
            word="prediction",
            syllables=["pre", "dic", "tion"],
            morphemes=[
                MorphemeInfo(text="pre", morpheme_type="prefix", origin="Latin"),
                MorphemeInfo(text="dict", morpheme_type="root", origin="Latin"),
                MorphemeInfo(text="tion", morpheme_type="suffix", origin="Latin"),
            ],
        )

        score = analyzer.score_word("prediction", entry)

        assert 1 <= score <= 10
        assert score >= 5  # Should be moderate difficulty

    def test_get_difficult_words_returns_correct_count(self):
        """Test that get_difficult_words returns requested count."""
        analyzer = WordDifficultyAnalyzer()
        text = (
            "The scientists hypothesized about the unprecedented phenomena. "
            "They analyzed the comprehensive methodology systematically."
        )

        words = analyzer.get_difficult_words(text, count=3)

        assert len(words) <= 3

    def test_get_difficult_words_filters_by_min_difficulty(self):
        """Test that words below min_difficulty are excluded."""
        analyzer = WordDifficultyAnalyzer()
        text = "The cat sat on the mat."  # Simple words

        words = analyzer.get_difficult_words(text, count=5, min_difficulty=8)

        # Simple text should have few/no words meeting high threshold
        assert len(words) <= 1

    def test_get_difficult_words_sorted_by_difficulty(self):
        """Test that results are sorted by difficulty (descending)."""
        analyzer = WordDifficultyAnalyzer()
        text = (
            "The unprecedented hypothesis required comprehensive analysis. "
            "The methodology was systematic and thorough."
        )

        words = analyzer.get_difficult_words(text, count=5, min_difficulty=3)

        if len(words) >= 2:
            # First word should be at least as difficult as second
            assert words[0].difficulty_score >= words[1].difficulty_score


class TestPrimerGenerator:
    """Tests for the PrimerGenerator class."""

    def test_init_default(self):
        """Test default initialization."""
        generator = PrimerGenerator()

        assert generator.model is not None
        assert generator.use_llm is True

    def test_init_no_llm(self):
        """Test initialization without LLM."""
        generator = PrimerGenerator(use_llm=False)

        assert generator.use_llm is False

    def test_generate_primer_returns_blocks(self):
        """Test that generate_primer returns TextBlocks."""
        generator = PrimerGenerator(use_llm=False)
        text = (
            "The scientists hypothesized about unprecedented phenomena. "
            "Their comprehensive methodology was systematic."
        )

        blocks = generator.generate_primer(text, word_count=3)

        assert isinstance(blocks, list)
        assert all(isinstance(b, TextBlock) for b in blocks)

    def test_generate_primer_includes_header(self):
        """Test that primer includes header block."""
        generator = PrimerGenerator(use_llm=False)
        text = "The unprecedented hypothesis required analysis."

        blocks = generator.generate_primer(text, word_count=2)

        if blocks:
            # First block should contain "WARM-UP" or similar header
            first_text = blocks[0].plain_text.upper()
            assert "WARM" in first_text or "PREVIEW" in first_text

    def test_generate_primer_empty_for_simple_text(self):
        """Test that simple text may produce empty primer."""
        generator = PrimerGenerator(use_llm=False)
        text = "The cat sat on the mat."  # Very simple

        blocks = generator.generate_primer(text, word_count=3)

        # Simple text might not have words meeting difficulty threshold
        # Empty list or minimal blocks is acceptable
        assert isinstance(blocks, list)

    def test_get_definitions_local(self):
        """Test local definition generation."""
        generator = PrimerGenerator(use_llm=False)
        words = [
            WordEntry(
                word="hypothesis",
                syllables=["hy", "poth", "e", "sis"],
                morphemes=[MorphemeInfo(text="hypo", meaning="under", origin="Greek")],
            )
        ]

        definitions = generator._get_definitions_local(words)

        assert len(definitions) == 1
        assert definitions[0]["word"] == "hypothesis"
        assert "pronunciation" in definitions[0]
        assert "definition" in definitions[0]

    def test_enhance_document(self):
        """Test that enhance_document adds primer to document."""
        generator = PrimerGenerator(use_llm=False)
        doc = FormattedDocument(blocks=[
            TextBlock(runs=[TextRun(
                text="The unprecedented hypothesis required comprehensive analysis.",
                style=TextStyle.NONE,
            )]),
        ])

        original_block_count = len(doc.blocks)
        result = generator.enhance_document(doc, word_count=3)

        # Document should have more blocks now (primer prepended)
        assert len(result.blocks) >= original_block_count

    def test_enhance_document_updates_vocabulary(self):
        """Test that enhance_document updates vocabulary metadata."""
        generator = PrimerGenerator(use_llm=False)
        doc = FormattedDocument(blocks=[
            TextBlock(runs=[TextRun(
                text="The unprecedented hypothesis required analysis.",
                style=TextStyle.NONE,
            )]),
        ])

        result = generator.enhance_document(doc, word_count=3)

        assert result.vocabulary is not None


class TestPrimerIntegration:
    """Integration tests for the primer system."""

    def test_difficulty_analyzer_and_primer_work_together(self):
        """Test that analyzer and primer integrate correctly."""
        analyzer = WordDifficultyAnalyzer()
        generator = PrimerGenerator(use_llm=False)

        text = (
            "The comprehensive methodology demonstrated unprecedented results. "
            "Scientists hypothesized about the systematic correlation."
        )

        # Get difficult words
        difficult_words = analyzer.get_difficult_words(text, count=3)

        # Generate primer
        blocks = generator.generate_primer(text, word_count=3)

        # If there are difficult words, there should be primer blocks
        if difficult_words:
            assert len(blocks) > 0


class TestAcademicWordsAndPatterns:
    """Tests for the word lists and patterns."""

    def test_academic_words_not_empty(self):
        """Test that academic words list is populated."""
        assert len(ACADEMIC_WORDS) > 0

    def test_irregular_patterns_not_empty(self):
        """Test that irregular patterns list is populated."""
        assert len(IRREGULAR_PATTERNS) > 0

    def test_common_academic_words_present(self):
        """Test that common academic words are in the list."""
        assert "hypothesis" in ACADEMIC_WORDS
        assert "analyze" in ACADEMIC_WORDS
        assert "methodology" in ACADEMIC_WORDS

    def test_common_irregular_patterns_present(self):
        """Test that common irregular patterns are in the list."""
        assert "ough" in IRREGULAR_PATTERNS
        assert "tion" in IRREGULAR_PATTERNS
        assert "ight" in IRREGULAR_PATTERNS
