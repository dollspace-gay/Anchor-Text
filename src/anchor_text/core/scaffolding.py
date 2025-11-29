"""Dynamic Scaffolding System for adaptive reading support.

This module implements the Adaptive Fading engine that tracks word exposure
and gradually reduces formatting support as words become familiar to the reader.
"""

import re
from collections import Counter
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class FadingProfile(str, Enum):
    """Profiles for how aggressively to fade scaffolding support."""

    STATIC = "static"  # No fading - same support throughout
    GENTLE = "gentle"  # Slow fading - 5 exposures before fade
    ADAPTIVE = "adaptive"  # Standard fading - 3 exposures before fade
    AGGRESSIVE = "aggressive"  # Fast fading - 2 exposures before fade


# Default exposure thresholds for each profile
PROFILE_THRESHOLDS = {
    FadingProfile.STATIC: float("inf"),  # Never fade
    FadingProfile.GENTLE: 5,
    FadingProfile.ADAPTIVE: 3,
    FadingProfile.AGGRESSIVE: 2,
}


@dataclass
class WordExposure:
    """Tracks exposure data for a single word."""

    word: str
    count: int = 0
    first_chunk: int = 0
    last_chunk: int = 0
    formatted_count: int = 0  # Times shown with formatting


@dataclass
class ScaffoldingContext:
    """Tracks word exposure and manages adaptive scaffolding.

    The context maintains a "memory" of words the reader has encountered,
    tracking how many times each word appears. Once a word reaches the
    exposure threshold, it is considered "mastered" and formatting support
    is faded (removed) for subsequent occurrences.

    Attributes:
        profile: The fading profile controlling how quickly support fades
        threshold: Number of exposures before a word is considered mastered
        word_exposures: Dictionary tracking exposure data per word
        current_chunk: Index of the current chunk being processed
    """

    profile: FadingProfile = FadingProfile.ADAPTIVE
    threshold: Optional[int] = None
    word_exposures: dict[str, WordExposure] = field(default_factory=dict)
    current_chunk: int = 0
    _min_word_length: int = 4  # Only track words with 4+ characters

    def __post_init__(self) -> None:
        """Set threshold based on profile if not explicitly provided."""
        if self.threshold is None:
            self.threshold = PROFILE_THRESHOLDS.get(
                self.profile, PROFILE_THRESHOLDS[FadingProfile.ADAPTIVE]
            )

    def extract_words(self, text: str) -> list[str]:
        """Extract meaningful words from text for tracking.

        Args:
            text: The text to extract words from

        Returns:
            List of lowercase words (4+ characters, alphabetic only)
        """
        # Remove formatting markers and special characters
        clean_text = re.sub(r"[·\*\[\]()]", " ", text)
        # Extract words
        words = re.findall(r"\b[a-zA-Z]+\b", clean_text)
        # Filter to meaningful words (4+ chars) and lowercase
        return [w.lower() for w in words if len(w) >= self._min_word_length]

    def update_exposure(self, text: str) -> None:
        """Update word exposure counts from processed text.

        Call this after each chunk is transformed to update the
        reader's "exposure history".

        Args:
            text: The text that was just processed (original, not transformed)
        """
        words = self.extract_words(text)
        word_counts = Counter(words)

        for word, count in word_counts.items():
            if word not in self.word_exposures:
                self.word_exposures[word] = WordExposure(
                    word=word,
                    count=count,
                    first_chunk=self.current_chunk,
                    last_chunk=self.current_chunk,
                )
            else:
                exposure = self.word_exposures[word]
                exposure.count += count
                exposure.last_chunk = self.current_chunk

        self.current_chunk += 1

    def is_mastered(self, word: str) -> bool:
        """Check if a word has been seen enough times to be "mastered".

        Args:
            word: The word to check

        Returns:
            True if the word has reached the exposure threshold
        """
        word_lower = word.lower()
        if word_lower not in self.word_exposures:
            return False

        exposure = self.word_exposures[word_lower]
        return exposure.count >= self.threshold

    def get_faded_words(self) -> set[str]:
        """Get the set of words that should have formatting removed.

        These are words the reader has seen enough times that they
        should be able to decode independently.

        Returns:
            Set of lowercase words that have reached mastery threshold
        """
        if self.profile == FadingProfile.STATIC:
            return set()

        return {
            word
            for word, exposure in self.word_exposures.items()
            if exposure.count >= self.threshold
        }

    def get_exposure_count(self, word: str) -> int:
        """Get the number of times a word has been seen.

        Args:
            word: The word to check

        Returns:
            Number of exposures, or 0 if never seen
        """
        word_lower = word.lower()
        if word_lower not in self.word_exposures:
            return 0
        return self.word_exposures[word_lower].count

    def mark_formatted(self, word: str) -> None:
        """Mark that a word was shown with formatting.

        Used to track how many times formatting was actually applied.

        Args:
            word: The word that was formatted
        """
        word_lower = word.lower()
        if word_lower in self.word_exposures:
            self.word_exposures[word_lower].formatted_count += 1

    def reset(self) -> None:
        """Reset all exposure data.

        Useful for starting a new document or testing.
        """
        self.word_exposures.clear()
        self.current_chunk = 0

    def get_stats(self) -> dict:
        """Get statistics about current scaffolding state.

        Returns:
            Dictionary with exposure statistics
        """
        total_words = len(self.word_exposures)
        mastered = len(self.get_faded_words())
        total_exposures = sum(e.count for e in self.word_exposures.values())

        return {
            "profile": self.profile.value,
            "threshold": self.threshold,
            "total_unique_words": total_words,
            "mastered_words": mastered,
            "total_exposures": total_exposures,
            "chunks_processed": self.current_chunk,
            "mastery_rate": mastered / total_words if total_words > 0 else 0,
        }

    def format_exclusion_prompt(self) -> str:
        """Generate prompt text instructing LLM to exclude mastered words.

        Returns:
            Prompt snippet to append to system prompt, or empty string if no exclusions
        """
        faded = self.get_faded_words()
        if not faded:
            return ""

        # Limit to most common faded words to avoid overwhelming the prompt
        sorted_faded = sorted(
            faded,
            key=lambda w: self.word_exposures[w].count,
            reverse=True,
        )[:50]  # Top 50 most seen words

        word_list = ", ".join(sorted_faded)
        return f"""

## MASTERED WORDS (Do NOT format these - write them normally):
The reader has seen these words multiple times and should decode them independently.
Do NOT apply syllable dots, bold roots, or other formatting to: {word_list}
"""
