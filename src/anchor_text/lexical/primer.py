"""Pre-Reading Primer generator.

This module implements the Pre-Reading Primer system, which generates
a warm-up section at the beginning of transformed documents containing
the most difficult words with pronunciation guides and practice exercises.
"""

from typing import Optional

from litellm import completion

from anchor_text.config import get_settings
from anchor_text.formatting.ir import (
    FormattedDocument,
    TextBlock,
    TextRun,
    TextStyle,
    WordEntry,
    MorphemeInfo,
    VocabularyMetadata,
)
from anchor_text.lexical.analyzer import LexicalAnalyzer


# Academic word list - commonly difficult words in educational texts
ACADEMIC_WORDS = {
    "analyze", "approach", "area", "assess", "assume", "authority", "available",
    "benefit", "concept", "consist", "constitute", "context", "contract", "create",
    "data", "define", "derive", "distribute", "economy", "environment", "establish",
    "estimate", "evident", "export", "factor", "finance", "formula", "function",
    "identify", "income", "indicate", "individual", "interpret", "involve", "issue",
    "labor", "legal", "legislate", "major", "method", "occur", "percent", "period",
    "policy", "principle", "proceed", "process", "require", "research", "respond",
    "role", "section", "sector", "significant", "similar", "source", "specific",
    "structure", "theory", "vary", "hypothesis", "phenomenon", "paradigm",
    "methodology", "synthesis", "correlation", "comprehensive", "fundamental",
}

# Irregular phonetic patterns that make words harder to decode
IRREGULAR_PATTERNS = [
    "ough",  # through, though, thought, rough
    "tion",  # nation (sounds like "shun")
    "sion",  # vision, tension
    "ight",  # light, night
    "eigh",  # weigh, neighbor
    "augh",  # caught, daughter
    "ious",  # various, curious
    "eous",  # gorgeous, courageous
    "ible",  # possible, terrible
    "able",  # when pronunciation varies
    "ture",  # nature, creature
    "sure",  # measure, treasure
    "que",   # technique, unique
    "gue",   # dialogue, catalogue
    "ph",    # phone, graph
    "psy",   # psychology
    "pneum", # pneumonia
    "kn",    # know, knife
    "wr",    # write, wrong
    "gn",    # sign, gnaw
    "mb",    # climb, thumb
    "bt",    # doubt, subtle
]


class WordDifficultyAnalyzer:
    """Analyzes word difficulty for pre-reading primer selection."""

    def __init__(self) -> None:
        """Initialize the difficulty analyzer."""
        self.academic_words = ACADEMIC_WORDS
        self.irregular_patterns = IRREGULAR_PATTERNS

    def score_word(self, word: str, entry: Optional[WordEntry] = None) -> int:
        """Score a word's difficulty on a 1-10 scale.

        Factors:
        - Syllable count (more syllables = harder)
        - Irregular phonetic patterns
        - Academic vocabulary status
        - Word length
        - Morpheme complexity

        Args:
            word: The word to score
            entry: Optional WordEntry with additional analysis

        Returns:
            Difficulty score from 1-10
        """
        word_lower = word.lower()
        score = 1.0  # Base score

        # Syllable count factor
        syllables = entry.syllables if entry else self._estimate_syllables(word)
        syllable_count = len(syllables) if isinstance(syllables, list) else syllables
        if syllable_count >= 4:
            score += 3
        elif syllable_count >= 3:
            score += 2
        elif syllable_count >= 2:
            score += 1

        # Length factor
        if len(word) > 10:
            score += 1.5
        elif len(word) > 7:
            score += 0.5

        # Irregular phonetics factor
        for pattern in self.irregular_patterns:
            if pattern in word_lower:
                score += 1.5
                break  # Only count once

        # Academic vocabulary factor
        if word_lower in self.academic_words:
            score += 2

        # Morpheme complexity (if available)
        if entry and entry.morphemes:
            if len(entry.morphemes) >= 3:
                score += 1
            # Greek/Latin roots are harder
            for m in entry.morphemes:
                if m.origin in ("Greek", "Latin"):
                    score += 0.3

        # Cap at 10
        return min(10, max(1, int(score)))

    def _estimate_syllables(self, word: str) -> int:
        """Estimate syllable count using vowel groups."""
        word = word.lower()
        count = 0
        prev_vowel = False

        for char in word:
            is_vowel = char in "aeiouy"
            if is_vowel and not prev_vowel:
                count += 1
            prev_vowel = is_vowel

        # Adjust for silent e
        if word.endswith("e") and count > 1:
            count -= 1

        return max(1, count)

    def get_difficult_words(
        self,
        text: str,
        count: int = 5,
        min_difficulty: int = 5,
    ) -> list[WordEntry]:
        """Extract the most difficult words from text.

        Args:
            text: The text to analyze
            count: Number of difficult words to return
            min_difficulty: Minimum difficulty score to include

        Returns:
            List of WordEntry objects for difficult words
        """
        analyzer = LexicalAnalyzer(use_llm=False)
        words = analyzer.extract_words(text, min_syllables=2)

        # Analyze and score each word
        entries: list[WordEntry] = []
        for word in words:
            entry = analyzer._analyze_word_locally(word)
            entry.difficulty_score = self.score_word(word, entry)
            if entry.difficulty_score >= min_difficulty:
                entries.append(entry)

        # Sort by difficulty (descending) and return top N
        entries.sort(key=lambda e: -e.difficulty_score)
        return entries[:count]


PRIMER_PROMPT = '''You are a vocabulary instruction specialist.

Create a brief pronunciation guide and definition for each word below.
Format as JSON array:

```json
[
  {
    "word": "hypothesis",
    "pronunciation": "hy-POTH-eh-sis",
    "definition": "an educated guess or proposed explanation",
    "example": "The scientist's hypothesis was proven correct."
  }
]
```

Guidelines:
- Pronunciation: Use hyphens for syllables, CAPS for stressed syllable
- Definition: Simple, clear, one sentence
- Example: Short sentence using the word naturally

Words to define:
'''


class PrimerGenerator:
    """Generates pre-reading primer sections."""

    def __init__(
        self,
        model: Optional[str] = None,
        use_llm: bool = True,
    ) -> None:
        """Initialize the primer generator.

        Args:
            model: LLM model for generating definitions
            use_llm: Whether to use LLM for definitions
        """
        settings = get_settings()
        self.model = model or settings.default_model
        self.use_llm = use_llm
        self.difficulty_analyzer = WordDifficultyAnalyzer()

    def generate_primer(
        self,
        text: str,
        word_count: int = 5,
    ) -> list[TextBlock]:
        """Generate primer blocks for a document.

        Args:
            text: The document text to analyze
            word_count: Number of difficult words to include

        Returns:
            List of TextBlocks for the primer section
        """
        # Get difficult words
        difficult_words = self.difficulty_analyzer.get_difficult_words(
            text, count=word_count, min_difficulty=5
        )

        if not difficult_words:
            return []

        blocks: list[TextBlock] = []

        # Header
        header = TextBlock()
        header.append("WARM-UP: Preview These Words", TextStyle.BOLD)
        blocks.append(header)

        intro = TextBlock()
        intro.append(
            "Before reading, practice these challenging words. "
            "Say each word aloud, breaking it into syllables."
        )
        blocks.append(intro)

        # Get definitions if using LLM
        if self.use_llm:
            definitions = self._get_definitions_llm(difficult_words)
        else:
            definitions = self._get_definitions_local(difficult_words)

        # Word entries
        for entry, defn in zip(difficult_words, definitions):
            blocks.extend(self._format_word_entry(entry, defn))

        # Practice section
        blocks.extend(self._generate_practice_section(difficult_words))

        # Separator
        separator = TextBlock()
        separator.append("─" * 40)
        blocks.append(separator)

        return blocks

    def _get_definitions_llm(
        self, words: list[WordEntry]
    ) -> list[dict]:
        """Get definitions using LLM."""
        import json
        import re

        word_list = "\n".join(w.word for w in words)
        prompt = PRIMER_PROMPT + word_list

        try:
            response = completion(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=1500,
            )
            content = response.choices[0].message.content
            if content:
                # Clean markdown wrapper
                content = content.strip()
                if content.startswith("```"):
                    content = re.sub(r"^```(?:json)?\n?", "", content)
                    content = re.sub(r"\n?```$", "", content)
                return json.loads(content)
        except Exception:
            pass

        return self._get_definitions_local(words)

    def _get_definitions_local(self, words: list[WordEntry]) -> list[dict]:
        """Generate basic definitions locally without LLM."""
        definitions = []
        for entry in words:
            # Basic pronunciation from syllables
            syllables = entry.syllables if entry.syllables else [entry.word]
            # Capitalize likely stressed syllable (usually second-to-last for multisyllabic)
            if len(syllables) > 1:
                stress_idx = max(0, len(syllables) - 2)
                syllables = [
                    s.upper() if i == stress_idx else s
                    for i, s in enumerate(syllables)
                ]
            pronunciation = "-".join(syllables)

            # Build definition from morphemes if available
            if entry.morphemes:
                meaning_parts = []
                for m in entry.morphemes:
                    if m.meaning:
                        meaning_parts.append(m.meaning)
                if meaning_parts:
                    definition = f"Related to: {', '.join(meaning_parts)}"
                else:
                    definition = f"A {len(entry.syllables)}-syllable word"
            else:
                definition = f"A {len(syllables)}-syllable word to practice"

            definitions.append({
                "word": entry.word,
                "pronunciation": pronunciation,
                "definition": definition,
                "example": f"Practice saying: {entry.word}",
            })

        return definitions

    def _format_word_entry(
        self, entry: WordEntry, definition: dict
    ) -> list[TextBlock]:
        """Format a single word entry for the primer."""
        blocks: list[TextBlock] = []

        # Word with syllables
        word_block = TextBlock()
        word_block.append(entry.syllable_text, TextStyle.BOLD)
        word_block.append(f"  [{definition.get('pronunciation', '')}]", TextStyle.ITALIC)
        blocks.append(word_block)

        # Definition
        def_block = TextBlock()
        def_block.append(f"  {definition.get('definition', '')}")
        blocks.append(def_block)

        # Example sentence
        if definition.get("example"):
            ex_block = TextBlock()
            ex_block.append(f'  Example: "{definition["example"]}"', TextStyle.ITALIC)
            blocks.append(ex_block)

        return blocks

    def _generate_practice_section(
        self, words: list[WordEntry]
    ) -> list[TextBlock]:
        """Generate a quick practice exercise."""
        blocks: list[TextBlock] = []

        practice_header = TextBlock()
        practice_header.append("Quick Practice", TextStyle.BOLD)
        blocks.append(practice_header)

        # Syllable counting exercise
        count_block = TextBlock()
        count_block.append("Count the syllables in each word:")
        blocks.append(count_block)

        for entry in words[:3]:
            line = TextBlock()
            # Show word without syllable dots
            line.append(f"  {entry.word}: ____ syllables")
            blocks.append(line)

        # Answer key
        answers = ", ".join(
            f"{w.word}={len(w.syllables)}" for w in words[:3]
        )
        answer_block = TextBlock()
        answer_block.append(f"(Answers: {answers})", TextStyle.ITALIC)
        blocks.append(answer_block)

        return blocks

    def enhance_document(
        self,
        doc: FormattedDocument,
        word_count: int = 5,
    ) -> FormattedDocument:
        """Add pre-reading primer to the beginning of a document.

        Args:
            doc: The document to enhance
            word_count: Number of difficult words to include

        Returns:
            Document with primer prepended
        """
        # Generate primer from document text
        primer_blocks = self.generate_primer(doc.plain_text, word_count)

        if primer_blocks:
            # Prepend primer blocks to document
            doc.blocks = primer_blocks + doc.blocks

            # Update vocabulary metadata
            if doc.vocabulary is None:
                doc.vocabulary = VocabularyMetadata()

            # Store pre-reading words
            difficult_words = self.difficulty_analyzer.get_difficult_words(
                doc.plain_text, count=word_count
            )
            doc.vocabulary.pre_reading_words = difficult_words

        return doc
