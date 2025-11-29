"""Companion Guide Generator for Lexical Cartography.

Generates a vocabulary guide document from the lexical analysis,
including Root Key, difficulty tiers, and morpheme families.
"""

from pathlib import Path
from typing import Optional

from anchor_text.formatting.ir import (
    FormattedDocument,
    TextBlock,
    TextRun,
    TextStyle,
    LexicalMap,
    MorphemeFamily,
    WordEntry,
)


class CompanionGuideGenerator:
    """Generates a companion vocabulary guide from lexical analysis."""

    def __init__(self, include_exercises: bool = True) -> None:
        """Initialize the guide generator.

        Args:
            include_exercises: Whether to include practice exercises
        """
        self.include_exercises = include_exercises

    def generate(
        self,
        lexical_map: LexicalMap,
        source_title: str = "Document",
    ) -> FormattedDocument:
        """Generate a companion guide document.

        Args:
            lexical_map: The lexical analysis to use
            source_title: Title of the source document

        Returns:
            FormattedDocument containing the guide
        """
        blocks: list[TextBlock] = []

        # Title
        title_block = TextBlock()
        title_block.append(f"Vocabulary Guide: {source_title}", TextStyle.BOLD)
        blocks.append(title_block)

        # Introduction
        intro = TextBlock()
        intro.append(
            f"This guide contains {lexical_map.total_unique_words} vocabulary words "
            f"organized by difficulty and root families. Use it to preview challenging "
            f"words before reading or to review afterward."
        )
        blocks.append(intro)

        # Section: Difficulty Tiers
        blocks.extend(self._generate_difficulty_section(lexical_map))

        # Section: Root Families (Root Key)
        blocks.extend(self._generate_root_key_section(lexical_map))

        # Section: Practice Exercises (optional)
        if self.include_exercises:
            blocks.extend(self._generate_exercises_section(lexical_map))

        # Section: Complete Word List
        blocks.extend(self._generate_word_list_section(lexical_map))

        return FormattedDocument(
            blocks=blocks,
            metadata={"type": "companion_guide", "source": source_title},
        )

    def _generate_difficulty_section(self, lexical_map: LexicalMap) -> list[TextBlock]:
        """Generate the difficulty tiers section."""
        blocks: list[TextBlock] = []

        # Section header
        header = TextBlock()
        header.append("Words by Difficulty", TextStyle.BOLD)
        blocks.append(header)

        # Challenging words (7-10)
        if lexical_map.difficulty_tiers["challenging"]:
            tier_block = TextBlock()
            tier_block.append("Challenging Words (Preview These First)", TextStyle.BOLD | TextStyle.ITALIC)
            blocks.append(tier_block)

            for word_key in lexical_map.difficulty_tiers["challenging"][:15]:
                entry = lexical_map.words.get(word_key)
                if entry:
                    blocks.append(self._format_word_entry(entry))

        # Medium difficulty (4-6)
        if lexical_map.difficulty_tiers["medium"]:
            tier_block = TextBlock()
            tier_block.append("Medium Difficulty", TextStyle.BOLD)
            blocks.append(tier_block)

            word_line = TextBlock()
            words = [lexical_map.words[k].word for k in lexical_map.difficulty_tiers["medium"][:20]]
            word_line.append(" · ".join(words))
            blocks.append(word_line)

        # Easy words (1-3)
        if lexical_map.difficulty_tiers["easy"]:
            tier_block = TextBlock()
            tier_block.append("Easier Words", TextStyle.BOLD)
            blocks.append(tier_block)

            word_line = TextBlock()
            words = [lexical_map.words[k].word for k in lexical_map.difficulty_tiers["easy"][:20]]
            word_line.append(" · ".join(words))
            blocks.append(word_line)

        return blocks

    def _generate_root_key_section(self, lexical_map: LexicalMap) -> list[TextBlock]:
        """Generate the Root Key section showing morpheme families."""
        blocks: list[TextBlock] = []

        # Section header
        header = TextBlock()
        header.append("Root Key: Word Families", TextStyle.BOLD)
        blocks.append(header)

        intro = TextBlock()
        intro.append(
            "Words that share a root have related meanings. Learning one root "
            "helps you decode many words!"
        )
        blocks.append(intro)

        families = lexical_map.get_root_families()

        for family in families[:10]:  # Top 10 families
            blocks.extend(self._format_family(family))

        return blocks

    def _format_family(self, family: MorphemeFamily) -> list[TextBlock]:
        """Format a morpheme family for display."""
        blocks: list[TextBlock] = []

        # Root header with meaning
        root_block = TextBlock()
        root_block.append(family.root.text.upper(), TextStyle.BOLD)
        if family.root.meaning:
            root_block.append(f" = {family.root.meaning}")
        if family.root.origin:
            root_block.append(f" ({family.root.origin})", TextStyle.ITALIC)
        blocks.append(root_block)

        # Family words
        words_block = TextBlock()
        word_texts = []
        for entry in family.words[:8]:  # Limit to 8 words per family
            word_texts.append(entry.syllable_text)
        words_block.append("  → " + ", ".join(word_texts))
        blocks.append(words_block)

        return blocks

    def _format_word_entry(self, entry: WordEntry) -> TextBlock:
        """Format a single word entry with syllables and meaning."""
        block = TextBlock()

        # Word with syllables
        block.append(entry.syllable_text, TextStyle.BOLD)

        # Morpheme breakdown if available
        if entry.morphemes:
            morpheme_parts = []
            for m in entry.morphemes:
                if m.meaning:
                    morpheme_parts.append(f"{m.text} ({m.meaning})")
            if morpheme_parts:
                block.append(f" = {' + '.join(morpheme_parts)}")

        return block

    def _generate_exercises_section(self, lexical_map: LexicalMap) -> list[TextBlock]:
        """Generate practice exercises."""
        blocks: list[TextBlock] = []

        header = TextBlock()
        header.append("Practice Exercises", TextStyle.BOLD)
        blocks.append(header)

        # Exercise 1: Root matching
        ex1_header = TextBlock()
        ex1_header.append("1. Match the Root", TextStyle.BOLD)
        blocks.append(ex1_header)

        families = lexical_map.get_root_families()[:5]
        if families:
            ex1_intro = TextBlock()
            ex1_intro.append("Draw lines to connect words with their root meaning:")
            blocks.append(ex1_intro)

            # Left column: words
            for family in families:
                if family.words:
                    line = TextBlock()
                    line.append(f"  {family.words[0].word}  →  ____{family.root.meaning}____")
                    blocks.append(line)

        # Exercise 2: Syllable counting
        ex2_header = TextBlock()
        ex2_header.append("2. Count the Syllables", TextStyle.BOLD)
        blocks.append(ex2_header)

        challenging = [lexical_map.words[k] for k in lexical_map.difficulty_tiers["challenging"][:5]]
        if challenging:
            for entry in challenging:
                line = TextBlock()
                # Remove syllable dots for the exercise
                word_plain = entry.word
                line.append(f"  {word_plain}: ____ syllables")
                blocks.append(line)

            answer_line = TextBlock()
            answer_line.append("Answers: " + ", ".join(
                f"{e.word}={len(e.syllables)}" for e in challenging
            ), TextStyle.ITALIC)
            blocks.append(answer_line)

        return blocks

    def _generate_word_list_section(self, lexical_map: LexicalMap) -> list[TextBlock]:
        """Generate complete alphabetical word list."""
        blocks: list[TextBlock] = []

        header = TextBlock()
        header.append("Complete Word List", TextStyle.BOLD)
        blocks.append(header)

        # Sort words alphabetically
        sorted_words = sorted(lexical_map.words.values(), key=lambda w: w.word.lower())

        # Group by first letter
        current_letter = ""
        current_words: list[str] = []

        for entry in sorted_words:
            first = entry.word[0].upper()
            if first != current_letter:
                # Output previous group
                if current_words:
                    word_block = TextBlock()
                    word_block.append(", ".join(current_words))
                    blocks.append(word_block)
                # Start new group
                current_letter = first
                letter_block = TextBlock()
                letter_block.append(current_letter, TextStyle.BOLD)
                blocks.append(letter_block)
                current_words = []

            current_words.append(entry.syllable_text)

        # Output last group
        if current_words:
            word_block = TextBlock()
            word_block.append(", ".join(current_words))
            blocks.append(word_block)

        return blocks

    def save_as_text(self, guide: FormattedDocument, path: Path) -> None:
        """Save the guide as a plain text file.

        Args:
            guide: The generated guide document
            path: Path to save the text file
        """
        lines = []
        for block in guide.blocks:
            line = ""
            for run in block.runs:
                text = run.text
                if run.bold and run.italic:
                    text = f"***{text}***"
                elif run.bold:
                    text = f"**{text}**"
                elif run.italic:
                    text = f"*{text}*"
                line += text
            lines.append(line)

        path.write_text("\n\n".join(lines), encoding="utf-8")
