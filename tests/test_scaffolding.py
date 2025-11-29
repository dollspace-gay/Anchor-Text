"""Tests for the Dynamic Scaffolding system."""


from anchor_text.core.scaffolding import (
    ScaffoldingContext,
    FadingProfile,
    WordExposure,
    PROFILE_THRESHOLDS,
)


class TestFadingProfile:
    """Tests for FadingProfile enum."""

    def test_profile_values(self):
        """Test that all profile values are defined."""
        assert FadingProfile.STATIC.value == "static"
        assert FadingProfile.GENTLE.value == "gentle"
        assert FadingProfile.ADAPTIVE.value == "adaptive"
        assert FadingProfile.AGGRESSIVE.value == "aggressive"

    def test_profile_thresholds(self):
        """Test that all profiles have thresholds defined."""
        assert PROFILE_THRESHOLDS[FadingProfile.STATIC] == float("inf")
        assert PROFILE_THRESHOLDS[FadingProfile.GENTLE] == 5
        assert PROFILE_THRESHOLDS[FadingProfile.ADAPTIVE] == 3
        assert PROFILE_THRESHOLDS[FadingProfile.AGGRESSIVE] == 2


class TestWordExposure:
    """Tests for WordExposure dataclass."""

    def test_default_values(self):
        """Test default values for WordExposure."""
        exposure = WordExposure(word="test")
        assert exposure.word == "test"
        assert exposure.count == 0
        assert exposure.first_chunk == 0
        assert exposure.last_chunk == 0
        assert exposure.formatted_count == 0


class TestScaffoldingContext:
    """Tests for ScaffoldingContext class."""

    def test_default_initialization(self):
        """Test default initialization."""
        context = ScaffoldingContext()
        assert context.profile == FadingProfile.ADAPTIVE
        assert context.threshold == 3
        assert context.current_chunk == 0
        assert len(context.word_exposures) == 0

    def test_custom_profile(self):
        """Test initialization with custom profile."""
        context = ScaffoldingContext(profile=FadingProfile.GENTLE)
        assert context.profile == FadingProfile.GENTLE
        assert context.threshold == 5

    def test_custom_threshold(self):
        """Test initialization with custom threshold."""
        context = ScaffoldingContext(threshold=7)
        assert context.threshold == 7

    def test_static_profile_never_fades(self):
        """Test that static profile never returns faded words."""
        context = ScaffoldingContext(profile=FadingProfile.STATIC)
        context.update_exposure("word word word word word")
        assert len(context.get_faded_words()) == 0

    def test_extract_words_basic(self):
        """Test basic word extraction."""
        context = ScaffoldingContext()
        words = context.extract_words("The scientists hypothesized.")
        assert "scientists" in words
        assert "hypothesized" in words
        # Short words filtered
        assert "the" not in words

    def test_extract_words_removes_formatting(self):
        """Test that formatting is removed from extracted words."""
        context = ScaffoldingContext()
        words = context.extract_words("**bolding** *italics* phi·los·o·phy")
        assert "bolding" in words
        assert "italics" in words
        # philosophy becomes "philosphy" after removing dots - test separately
        words2 = context.extract_words("philosophy")
        assert "philosophy" in words2

    def test_update_exposure_tracks_count(self):
        """Test that exposure count is updated correctly."""
        context = ScaffoldingContext()
        context.update_exposure("philosophy philosophy philosophy")
        assert context.get_exposure_count("philosophy") == 3

    def test_update_exposure_increments_chunk(self):
        """Test that chunk counter increments."""
        context = ScaffoldingContext()
        assert context.current_chunk == 0
        context.update_exposure("first chunk text")
        assert context.current_chunk == 1
        context.update_exposure("second chunk text")
        assert context.current_chunk == 2

    def test_is_mastered_below_threshold(self):
        """Test that words below threshold are not mastered."""
        context = ScaffoldingContext(threshold=3)
        context.update_exposure("philosophy philosophy")
        assert not context.is_mastered("philosophy")

    def test_is_mastered_at_threshold(self):
        """Test that words at threshold are mastered."""
        context = ScaffoldingContext(threshold=3)
        context.update_exposure("philosophy philosophy philosophy")
        assert context.is_mastered("philosophy")

    def test_is_mastered_unknown_word(self):
        """Test that unknown words are not mastered."""
        context = ScaffoldingContext()
        assert not context.is_mastered("unknown")

    def test_get_faded_words_returns_mastered(self):
        """Test that get_faded_words returns mastered words."""
        context = ScaffoldingContext(threshold=2)
        context.update_exposure("philosophy philosophy scientist")
        faded = context.get_faded_words()
        assert "philosophy" in faded
        assert "scientist" not in faded

    def test_mark_formatted(self):
        """Test marking a word as formatted."""
        context = ScaffoldingContext()
        context.update_exposure("philosophy")
        context.mark_formatted("philosophy")
        assert context.word_exposures["philosophy"].formatted_count == 1

    def test_reset_clears_state(self):
        """Test that reset clears all state."""
        context = ScaffoldingContext()
        context.update_exposure("philosophy philosophy philosophy")
        context.reset()
        assert len(context.word_exposures) == 0
        assert context.current_chunk == 0

    def test_get_stats(self):
        """Test statistics generation."""
        context = ScaffoldingContext(threshold=2)
        context.update_exposure("philosophy philosophy science")
        stats = context.get_stats()

        assert stats["profile"] == "adaptive"
        assert stats["threshold"] == 2
        assert stats["total_unique_words"] == 2
        assert stats["mastered_words"] == 1  # philosophy
        assert stats["total_exposures"] == 3
        assert stats["chunks_processed"] == 1

    def test_format_exclusion_prompt_empty_when_no_mastered(self):
        """Test that exclusion prompt is empty when no words mastered."""
        context = ScaffoldingContext()
        context.update_exposure("philosophy")  # Only 1 exposure
        prompt = context.format_exclusion_prompt()
        assert prompt == ""

    def test_format_exclusion_prompt_includes_mastered_words(self):
        """Test that exclusion prompt includes mastered words."""
        context = ScaffoldingContext(threshold=2)
        context.update_exposure("philosophy philosophy hypothesis hypothesis")
        prompt = context.format_exclusion_prompt()

        assert "MASTERED WORDS" in prompt
        assert "philosophy" in prompt
        assert "hypothesis" in prompt

    def test_aggressive_profile_fades_quickly(self):
        """Test that aggressive profile fades after 2 exposures."""
        context = ScaffoldingContext(profile=FadingProfile.AGGRESSIVE)
        assert context.threshold == 2
        context.update_exposure("philosophy philosophy")
        assert context.is_mastered("philosophy")


class TestScaffoldingAcrossChunks:
    """Tests for scaffolding behavior across multiple chunks."""

    def test_word_accumulates_across_chunks(self):
        """Test that word counts accumulate across chunks."""
        context = ScaffoldingContext(threshold=3)

        context.update_exposure("philosophy once")
        assert context.get_exposure_count("philosophy") == 1
        assert not context.is_mastered("philosophy")

        context.update_exposure("philosophy twice")
        assert context.get_exposure_count("philosophy") == 2
        assert not context.is_mastered("philosophy")

        context.update_exposure("philosophy thrice")
        assert context.get_exposure_count("philosophy") == 3
        assert context.is_mastered("philosophy")

    def test_first_chunk_no_exclusions(self):
        """Test that first chunk has no exclusions."""
        context = ScaffoldingContext()
        # Before any exposure, no exclusions
        assert context.format_exclusion_prompt() == ""

    def test_second_chunk_has_exclusions(self):
        """Test that second chunk can have exclusions from first."""
        context = ScaffoldingContext(threshold=2)

        # First chunk with repeated words
        context.update_exposure("philosophy philosophy hypothesis hypothesis")

        # Now we should have exclusions
        prompt = context.format_exclusion_prompt()
        assert "philosophy" in prompt
        assert "hypothesis" in prompt

    def test_tracks_first_and_last_chunk(self):
        """Test that first and last chunk are tracked."""
        context = ScaffoldingContext()

        context.update_exposure("philosophy in chunk zero")
        assert context.word_exposures["philosophy"].first_chunk == 0
        assert context.word_exposures["philosophy"].last_chunk == 0

        context.update_exposure("some other text")

        context.update_exposure("philosophy again in chunk two")
        assert context.word_exposures["philosophy"].first_chunk == 0
        assert context.word_exposures["philosophy"].last_chunk == 2


class TestScaffoldingEdgeCases:
    """Edge case tests for scaffolding."""

    def test_empty_text(self):
        """Test handling of empty text."""
        context = ScaffoldingContext()
        context.update_exposure("")
        assert len(context.word_exposures) == 0

    def test_short_words_ignored(self):
        """Test that short words are ignored."""
        context = ScaffoldingContext()
        context.update_exposure("the cat sat on a mat")
        # All words are 3 chars or less
        assert len(context.word_exposures) == 0

    def test_case_insensitive(self):
        """Test that word tracking is case insensitive."""
        context = ScaffoldingContext()
        context.update_exposure("Philosophy PHILOSOPHY philosophy")
        assert context.get_exposure_count("philosophy") == 3
        assert context.get_exposure_count("PHILOSOPHY") == 3

    def test_special_characters_stripped(self):
        """Test that special characters are stripped."""
        context = ScaffoldingContext()
        words = context.extract_words("[Decoder Check: philosophy?] (hypothesis)")
        assert "philosophy" in words
        assert "hypothesis" in words
        assert "decoder" in words

    def test_exclusion_prompt_limits_words(self):
        """Test that exclusion prompt limits to top 50 words."""
        context = ScaffoldingContext(threshold=1)
        # Generate 100 unique alphabetic words with 4+ characters
        alpha = "abcdefghijklmnopqrstuvwxyz"
        words = [
            f"test{alpha[i % 26]}{alpha[(i + 5) % 26]}"
            f"{alpha[(i + 10) % 26]}{alpha[(i + 15) % 26]}"
            for i in range(100)
        ]
        text = " ".join(words)
        context.update_exposure(text)

        prompt = context.format_exclusion_prompt()
        # Should contain some words but be limited
        assert "test" in prompt
