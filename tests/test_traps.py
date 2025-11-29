"""Tests for the Enhanced Decoder Traps generator."""

import pytest
from unittest.mock import Mock, patch

from anchor_text.llm.traps import TrapGenerator, generate_lookalikes
from anchor_text.formatting.ir import (
    FormattedDocument,
    TextBlock,
    TextRun,
    TextStyle,
    DecoderTrap,
    TrapOption,
    VocabularyMetadata,
)


class TestGenerateLookalikes:
    """Tests for the generate_lookalikes function."""

    def test_prefix_substitution_hypo(self):
        """Test lookalike generation for hypo- prefix."""
        lookalikes = generate_lookalikes("hypothesis", count=2)
        assert len(lookalikes) >= 1
        # Should generate words starting with similar prefixes
        assert any(l.startswith("hyper") or l.startswith("hospi") for l in lookalikes)

    def test_prefix_substitution_pre(self):
        """Test lookalike generation for pre- prefix."""
        lookalikes = generate_lookalikes("predict", count=2)
        assert len(lookalikes) >= 1
        # Should generate words like protect, prodict, etc.
        assert any(l.startswith("pro") or l.startswith("per") for l in lookalikes)

    def test_suffix_substitution_tion(self):
        """Test lookalike generation for -tion suffix."""
        lookalikes = generate_lookalikes("celebration", count=2)
        assert len(lookalikes) >= 1

    def test_no_duplicate_of_original(self):
        """Test that lookalikes don't include the original word."""
        lookalikes = generate_lookalikes("consideration", count=5)
        assert "consideration" not in [l.lower() for l in lookalikes]

    def test_respects_count_limit(self):
        """Test that count parameter limits results."""
        lookalikes = generate_lookalikes("international", count=2)
        assert len(lookalikes) <= 2

    def test_short_word_fallback(self):
        """Test lookalike generation for short words uses letter swap."""
        lookalikes = generate_lookalikes("cat", count=2)
        # May return fewer or none for very short words
        assert isinstance(lookalikes, list)


class TestDecoderTrap:
    """Tests for the DecoderTrap dataclass."""

    def test_correct_answer_property(self):
        """Test that correct_answer returns the right option."""
        trap = DecoderTrap(
            question="What word means to guess?",
            target_word="hypothesized",
            options=[
                TrapOption(text="hospitalized", is_correct=False, is_lookalike=True),
                TrapOption(text="hypothesized", is_correct=True, is_lookalike=False),
                TrapOption(text="harmonized", is_correct=False, is_lookalike=True),
            ],
        )
        assert trap.correct_answer == "hypothesized"

    def test_correct_answer_none_when_missing(self):
        """Test correct_answer returns None when no correct option."""
        trap = DecoderTrap(
            question="Test question",
            target_word="test",
            options=[
                TrapOption(text="wrong1", is_correct=False),
                TrapOption(text="wrong2", is_correct=False),
            ],
        )
        assert trap.correct_answer is None

    def test_to_simple_text(self):
        """Test conversion to simple [Decoder Check: ...] format."""
        trap = DecoderTrap(
            question="What did the scientists do?",
            target_word="hypothesized",
        )
        result = trap.to_simple_text()
        assert result == "[Decoder Check: What did the scientists do?]"

    def test_to_interactive_html(self):
        """Test conversion to interactive HTML."""
        trap = DecoderTrap(
            question="What word means to guess?",
            target_word="hypothesized",
            explanation="The correct answer is hypothesized.",
            options=[
                TrapOption(text="hypothesized", is_correct=True, is_lookalike=False),
                TrapOption(text="hospitalized", is_correct=False, is_lookalike=True),
            ],
        )
        html = trap.to_interactive_html()

        assert 'class="decoder-trap"' in html
        assert 'data-target="hypothesized"' in html
        assert 'class="trap-question"' in html
        assert "What word means to guess?" in html
        assert 'class="trap-option correct"' in html
        assert 'class="trap-option lookalike"' in html
        assert "hypothesized" in html
        assert "hospitalized" in html


class TestTrapGenerator:
    """Tests for the TrapGenerator class."""

    def test_init_default_model(self):
        """Test that TrapGenerator uses default model from settings."""
        generator = TrapGenerator()
        assert generator.model is not None

    def test_init_custom_model(self):
        """Test that TrapGenerator accepts custom model."""
        generator = TrapGenerator(model="openai/gpt-4o")
        assert generator.model == "openai/gpt-4o"

    def test_extract_target_words_empty_doc(self):
        """Test extraction from document with no decoder traps."""
        generator = TrapGenerator()
        doc = FormattedDocument(blocks=[
            TextBlock(runs=[TextRun(text="Some text", style=TextStyle.NONE)]),
        ])
        targets = generator._extract_target_words(doc)
        assert targets == []

    def test_extract_target_words_with_trap(self):
        """Test extraction from document with decoder trap."""
        generator = TrapGenerator()
        doc = FormattedDocument(blocks=[
            TextBlock(runs=[TextRun(text="The scientists hypothesized.", style=TextStyle.NONE)]),
            TextBlock(
                runs=[TextRun(text="[Decoder Check: What did the scientists do?]", style=TextStyle.NONE)],
                is_decoder_trap=True,
            ),
        ])
        targets = generator._extract_target_words(doc)
        assert len(targets) == 1
        assert "hypothesized" in targets[0]["paragraph_text"]

    def test_fallback_simple_traps(self):
        """Test fallback trap generation when LLM fails."""
        generator = TrapGenerator()
        targets = [
            {
                "paragraph_index": 0,
                "paragraph_text": "The scientists hypothesized.",
                "existing_question": "[Decoder Check: What did the scientists do?]",
            }
        ]
        traps = generator._fallback_simple_traps(targets)

        assert len(traps) == 1
        assert traps[0].question == "What did the scientists do?"
        assert traps[0].paragraph_index == 0

    def test_parse_response_valid_json(self):
        """Test parsing valid JSON response."""
        generator = TrapGenerator()
        response = '''[{
            "paragraph_index": 0,
            "question": "What did the scientists do?",
            "target_word": "hypothesized",
            "correct_answer": "hypothesized",
            "distractors": [
                {"word": "hospitalized", "is_lookalike": true},
                {"word": "analyzed", "is_lookalike": false}
            ],
            "explanation": "Test explanation"
        }]'''

        targets = [{"paragraph_text": "Test", "existing_question": "Test?", "paragraph_index": 0}]
        traps = generator._parse_response(response, targets)

        assert len(traps) == 1
        assert traps[0].question == "What did the scientists do?"
        assert traps[0].target_word == "hypothesized"
        assert len(traps[0].options) == 3  # 1 correct + 2 distractors
        assert traps[0].explanation == "Test explanation"

    def test_parse_response_with_markdown_wrapper(self):
        """Test parsing JSON wrapped in markdown code blocks."""
        generator = TrapGenerator()
        response = '''```json
[{
    "paragraph_index": 0,
    "question": "Test question?",
    "target_word": "test",
    "correct_answer": "test",
    "distractors": []
}]
```'''
        targets = [{"paragraph_text": "Test", "existing_question": "Test?", "paragraph_index": 0}]
        traps = generator._parse_response(response, targets)

        assert len(traps) == 1
        assert traps[0].question == "Test question?"

    def test_parse_response_invalid_json_fallback(self):
        """Test that invalid JSON falls back to simple traps."""
        generator = TrapGenerator()
        response = "This is not valid JSON"
        targets = [
            {
                "paragraph_index": 0,
                "paragraph_text": "Test paragraph",
                "existing_question": "[Decoder Check: Test question?]",
            }
        ]
        traps = generator._parse_response(response, targets)

        # Should fall back to simple traps
        assert len(traps) == 1
        assert traps[0].question == "Test question?"

    def test_enhance_document_creates_vocabulary(self):
        """Test that enhance_document creates vocabulary metadata if missing."""
        generator = TrapGenerator()
        doc = FormattedDocument(blocks=[
            TextBlock(runs=[TextRun(text="Test text", style=TextStyle.NONE)]),
        ])
        assert doc.vocabulary is None

        # Mock generate_traps to avoid LLM call
        with patch.object(generator, 'generate_traps', return_value=[]):
            result = generator.enhance_document(doc)

        assert result.vocabulary is not None
        assert isinstance(result.vocabulary, VocabularyMetadata)

    def test_enhance_document_preserves_existing_vocabulary(self):
        """Test that enhance_document preserves existing vocabulary data."""
        generator = TrapGenerator()
        existing_vocab = VocabularyMetadata(scaffold_level=3)
        doc = FormattedDocument(
            blocks=[TextBlock(runs=[TextRun(text="Test", style=TextStyle.NONE)])],
            vocabulary=existing_vocab,
        )

        with patch.object(generator, 'generate_traps', return_value=[]):
            result = generator.enhance_document(doc)

        assert result.vocabulary.scaffold_level == 3


class TestTrapOption:
    """Tests for the TrapOption dataclass."""

    def test_default_values(self):
        """Test TrapOption default values."""
        option = TrapOption(text="test")
        assert option.text == "test"
        assert option.is_correct is False
        assert option.is_lookalike is False

    def test_correct_option(self):
        """Test TrapOption with is_correct=True."""
        option = TrapOption(text="answer", is_correct=True)
        assert option.is_correct is True

    def test_lookalike_option(self):
        """Test TrapOption with is_lookalike=True."""
        option = TrapOption(text="hospitalized", is_lookalike=True)
        assert option.is_lookalike is True
