"""Intermediate Representation for formatted text.

This module defines the data structures that bridge AI markdown output
to format-specific rendering. The IR allows consistent handling of
formatted text across all document formats.
"""

from dataclasses import dataclass, field
from enum import Flag, auto
from pathlib import Path
from typing import Optional


# =============================================================================
# Scaffolding Level Configuration
# =============================================================================

class ScaffoldLevel:
    """Scaffolding levels for graduated reading support.

    Level 1 (MAX): Full protocol - all formatting, syllable breaks, decoder traps
    Level 2 (HIGH): Remove syllable dots, keep bold/italic/traps
    Level 3 (MED): Remove root anchoring, keep syntactic spine/traps
    Level 4 (LOW): Remove syntactic spine, keep decoder traps only
    Level 5 (MIN): Plain text with minimal formatting
    """
    MAX = 1  # Full support
    HIGH = 2
    MED = 3
    LOW = 4
    MIN = 5  # Minimal support

    @classmethod
    def validate(cls, level: int) -> int:
        """Validate and clamp level to valid range."""
        return max(cls.MAX, min(cls.MIN, level))


class TextStyle(Flag):
    """Text styling flags (combinable with |)."""

    NONE = 0
    BOLD = auto()
    ITALIC = auto()


@dataclass
class TextRun:
    """A contiguous run of text with consistent styling.

    Attributes:
        text: The text content
        style: Combined style flags (BOLD, ITALIC, or both)
    """

    text: str
    style: TextStyle = TextStyle.NONE

    @property
    def bold(self) -> bool:
        """Check if this run is bold."""
        return TextStyle.BOLD in self.style

    @property
    def italic(self) -> bool:
        """Check if this run is italic."""
        return TextStyle.ITALIC in self.style

    def __str__(self) -> str:
        return self.text


@dataclass
class ImageRef:
    """Reference to an image extracted from a document.

    Attributes:
        data: Raw image bytes
        format: Image format (png, jpg, etc.)
        width: Original width in pixels (if known)
        height: Original height in pixels (if known)
        page: Page number where image appeared (for PDFs)
        position: Approximate position in text flow (index in blocks list)
    """

    data: bytes
    format: str = "png"
    width: Optional[int] = None
    height: Optional[int] = None
    page: Optional[int] = None
    position: int = 0

    def save(self, path: Path) -> None:
        """Save image data to a file."""
        path.write_bytes(self.data)


@dataclass
class TextBlock:
    """A paragraph/block of text containing multiple styled runs.

    Attributes:
        runs: List of TextRun objects making up this block
        is_decoder_trap: Whether this block is the Decoder's Trap question
    """

    runs: list[TextRun] = field(default_factory=list)
    is_decoder_trap: bool = False

    @property
    def plain_text(self) -> str:
        """Get the plain text content without styling."""
        return "".join(run.text for run in self.runs)

    def append(self, text: str, style: TextStyle = TextStyle.NONE) -> None:
        """Append a new run to this block."""
        self.runs.append(TextRun(text=text, style=style))

    def __str__(self) -> str:
        return self.plain_text


@dataclass
class FormattedDocument:
    """Complete formatted document ready for rendering.

    Attributes:
        blocks: List of text blocks (paragraphs)
        images: List of images extracted from the original document
        metadata: Additional metadata from the original document
        vocabulary: Vocabulary analysis and enhanced trap data (optional)
    """

    blocks: list[TextBlock] = field(default_factory=list)
    images: list[ImageRef] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    # Note: vocabulary is initialized as None, set to VocabularyMetadata when needed
    # Using string annotation for forward reference (VocabularyMetadata defined later)
    vocabulary: Optional["VocabularyMetadata"] = None

    @property
    def plain_text(self) -> str:
        """Get all text content without styling."""
        return "\n\n".join(block.plain_text for block in self.blocks)

    @property
    def has_decoder_trap(self) -> bool:
        """Check if document contains a Decoder's Trap."""
        return any(block.is_decoder_trap for block in self.blocks)

    def add_block(self, block: TextBlock) -> None:
        """Add a text block to the document."""
        self.blocks.append(block)

    def add_image(self, image: ImageRef) -> None:
        """Add an image reference to the document."""
        self.images.append(image)


# =============================================================================
# Enhanced Decoder Traps (System 3)
# =============================================================================

@dataclass
class TrapOption:
    """A single option in a decoder trap question.

    Attributes:
        text: The option text (e.g., "hypothesized")
        is_correct: Whether this is the correct answer
        is_lookalike: Whether this is a visually similar distractor
    """
    text: str
    is_correct: bool = False
    is_lookalike: bool = False


@dataclass
class DecoderTrap:
    """An enhanced decoder trap with multiple choice options.

    Attributes:
        question: The comprehension question
        target_word: The word being tested (from the paragraph)
        options: List of answer options (correct + distractors)
        paragraph_index: Index of the paragraph this trap follows
        explanation: Optional explanation for the correct answer
    """
    question: str
    target_word: str
    options: list[TrapOption] = field(default_factory=list)
    paragraph_index: int = 0
    explanation: str = ""

    @property
    def correct_answer(self) -> Optional[str]:
        """Get the correct answer text."""
        for opt in self.options:
            if opt.is_correct:
                return opt.text
        return None

    def to_simple_text(self) -> str:
        """Convert to simple [Decoder Check: ...] format."""
        return f"[Decoder Check: {self.question}]"

    def to_interactive_html(self) -> str:
        """Convert to interactive HTML with clickable options."""
        html_parts = [
            f'<div class="decoder-trap" data-target="{self.target_word}">',
            f'  <p class="trap-question">{self.question}</p>',
            '  <div class="trap-options">',
        ]
        for i, opt in enumerate(self.options):
            classes = ["trap-option"]
            if opt.is_correct:
                classes.append("correct")
            if opt.is_lookalike:
                classes.append("lookalike")
            html_parts.append(
                f'    <button class="{" ".join(classes)}" '
                f'data-index="{i}">{opt.text}</button>'
            )
        explanation_html = (
            f'  <p class="trap-explanation" style="display:none">'
            f'{self.explanation}</p>'
        )
        html_parts.extend([
            '  </div>',
            explanation_html,
            '</div>',
        ])
        return "\n".join(html_parts)


# =============================================================================
# Lexical Cartography (System 2)
# =============================================================================

@dataclass
class MorphemeInfo:
    """Information about a morpheme (root, prefix, or suffix).

    Attributes:
        text: The morpheme text (e.g., "dict" for "predict")
        meaning: The meaning of this morpheme
        origin: Language of origin (Latin, Greek, etc.)
        morpheme_type: "root", "prefix", or "suffix"
    """
    text: str
    meaning: str = ""
    origin: str = ""
    morpheme_type: str = "root"


@dataclass
class WordEntry:
    """A word entry in the lexical map.

    Attributes:
        word: The word as it appears in text
        root: The root morpheme
        morphemes: All morphemes that make up this word
        syllables: Syllable breakdown
        frequency: How many times this word appears in the document
        difficulty_score: Estimated reading difficulty (1-10)
        first_occurrence: Index of first paragraph containing this word
    """
    word: str
    root: str = ""
    morphemes: list[MorphemeInfo] = field(default_factory=list)
    syllables: list[str] = field(default_factory=list)
    frequency: int = 1
    difficulty_score: int = 5
    first_occurrence: int = 0

    @property
    def syllable_text(self) -> str:
        """Get word with syllable dots."""
        return "·".join(self.syllables) if self.syllables else self.word


@dataclass
class MorphemeFamily:
    """A family of words sharing a common root.

    Attributes:
        root: The root morpheme info
        words: Words in this family found in the document
        example_sentence: Example sentence using a word from this family
    """
    root: MorphemeInfo
    words: list[WordEntry] = field(default_factory=list)
    example_sentence: str = ""


@dataclass
class LexicalMap:
    """Complete lexical analysis of a document.

    This is the output of the Lexical Cartography system, containing
    all vocabulary analysis needed for the companion guide and
    targeted highlighting.

    Attributes:
        words: Dictionary of word -> WordEntry
        families: List of morpheme families (grouped by root)
        difficulty_tiers: Words grouped by difficulty (1-3, 4-6, 7-10)
        total_unique_words: Count of unique multisyllabic words
    """
    words: dict[str, WordEntry] = field(default_factory=dict)
    families: list[MorphemeFamily] = field(default_factory=list)
    difficulty_tiers: dict[str, list[str]] = field(default_factory=lambda: {
        "easy": [],      # 1-3
        "medium": [],    # 4-6
        "challenging": []  # 7-10
    })
    total_unique_words: int = 0

    def add_word(self, entry: WordEntry) -> None:
        """Add or update a word entry."""
        key = entry.word.lower()
        if key in self.words:
            self.words[key].frequency += 1
        else:
            self.words[key] = entry
            self.total_unique_words += 1
            # Categorize by difficulty
            if entry.difficulty_score <= 3:
                self.difficulty_tiers["easy"].append(key)
            elif entry.difficulty_score <= 6:
                self.difficulty_tiers["medium"].append(key)
            else:
                self.difficulty_tiers["challenging"].append(key)

    def get_root_families(self) -> list[MorphemeFamily]:
        """Group words by their root morphemes."""
        root_groups: dict[str, list[WordEntry]] = {}
        for entry in self.words.values():
            if entry.root:
                root_key = entry.root.lower()
                if root_key not in root_groups:
                    root_groups[root_key] = []
                root_groups[root_key].append(entry)

        families = []
        for root_text, words in root_groups.items():
            if len(words) >= 2:  # Only families with 2+ words
                root_info = MorphemeInfo(text=root_text, morpheme_type="root")
                # Try to get meaning from first word's morphemes
                for w in words:
                    for m in w.morphemes:
                        if m.text.lower() == root_text and m.meaning:
                            root_info.meaning = m.meaning
                            root_info.origin = m.origin
                            break
                    if root_info.meaning:
                        break
                families.append(MorphemeFamily(root=root_info, words=words))

        return sorted(families, key=lambda f: len(f.words), reverse=True)


@dataclass
class VocabularyMetadata:
    """Vocabulary metadata attached to a FormattedDocument.

    Attributes:
        lexical_map: The complete lexical analysis
        traps: Enhanced decoder traps for the document
        pre_reading_words: Words for the pre-reading primer section
        scaffold_level: Current scaffolding level (1-5)
    """
    lexical_map: Optional[LexicalMap] = None
    traps: list[DecoderTrap] = field(default_factory=list)
    pre_reading_words: list[WordEntry] = field(default_factory=list)
    scaffold_level: int = ScaffoldLevel.MAX
