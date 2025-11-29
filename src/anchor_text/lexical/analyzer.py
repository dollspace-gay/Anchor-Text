"""Lexical Analyzer for extracting and analyzing vocabulary from documents.

This module implements the core of the Lexical Cartography system,
extracting multisyllabic words, identifying morphemes, and building
a vocabulary map for the companion guide and targeted highlighting.
"""

import re
from typing import Optional

from litellm import completion

from anchor_text.config import get_settings
from anchor_text.formatting.ir import (
    FormattedDocument,
    LexicalMap,
    WordEntry,
    MorphemeInfo,
    MorphemeFamily,
    VocabularyMetadata,
)


# Common morphemes with meanings - used for local analysis
COMMON_PREFIXES = {
    "un": ("not", "Germanic"),
    "re": ("again, back", "Latin"),
    "pre": ("before", "Latin"),
    "dis": ("not, opposite", "Latin"),
    "mis": ("wrongly", "Germanic"),
    "over": ("too much", "Germanic"),
    "under": ("below", "Germanic"),
    "sub": ("under", "Latin"),
    "super": ("above", "Latin"),
    "inter": ("between", "Latin"),
    "trans": ("across", "Latin"),
    "anti": ("against", "Greek"),
    "auto": ("self", "Greek"),
    "bi": ("two", "Latin"),
    "tri": ("three", "Latin/Greek"),
    "multi": ("many", "Latin"),
    "semi": ("half", "Latin"),
    "hypo": ("under, below", "Greek"),
    "hyper": ("over, above", "Greek"),
    "ex": ("out, former", "Latin"),
    "in": ("not, into", "Latin"),
    "im": ("not", "Latin"),
    "ir": ("not", "Latin"),
    "il": ("not", "Latin"),
    "non": ("not", "Latin"),
    "co": ("together", "Latin"),
    "con": ("together", "Latin"),
    "com": ("together", "Latin"),
    "de": ("down, from", "Latin"),
    "pro": ("forward, for", "Latin"),
    "post": ("after", "Latin"),
}

COMMON_SUFFIXES = {
    "tion": ("act/state of", "Latin"),
    "sion": ("act/state of", "Latin"),
    "ment": ("act/state of", "Latin"),
    "ness": ("state of being", "Germanic"),
    "able": ("capable of", "Latin"),
    "ible": ("capable of", "Latin"),
    "ful": ("full of", "Germanic"),
    "less": ("without", "Germanic"),
    "ly": ("in manner of", "Germanic"),
    "er": ("one who", "Germanic"),
    "or": ("one who", "Latin"),
    "ist": ("one who", "Greek"),
    "ism": ("belief/practice", "Greek"),
    "ity": ("state of", "Latin"),
    "ty": ("state of", "Latin"),
    "ous": ("full of", "Latin"),
    "ious": ("full of", "Latin"),
    "eous": ("full of", "Latin"),
    "al": ("relating to", "Latin"),
    "ial": ("relating to", "Latin"),
    "ive": ("tending to", "Latin"),
    "ative": ("tending to", "Latin"),
    "ize": ("to make", "Greek"),
    "ise": ("to make", "Greek"),
    "en": ("to make", "Germanic"),
    "ate": ("to make, having", "Latin"),
    "ify": ("to make", "Latin"),
    "ward": ("direction", "Germanic"),
    "wise": ("manner", "Germanic"),
    "dom": ("state, realm", "Germanic"),
    "ship": ("state, skill", "Germanic"),
    "hood": ("state, condition", "Germanic"),
}

# Common roots (partial list - LLM will provide more)
COMMON_ROOTS = {
    "dict": ("say, speak", "Latin"),
    "scrib": ("write", "Latin"),
    "script": ("write", "Latin"),
    "port": ("carry", "Latin"),
    "ject": ("throw", "Latin"),
    "duct": ("lead", "Latin"),
    "struct": ("build", "Latin"),
    "tract": ("pull, draw", "Latin"),
    "spec": ("see, look", "Latin"),
    "spect": ("see, look", "Latin"),
    "vid": ("see", "Latin"),
    "vis": ("see", "Latin"),
    "aud": ("hear", "Latin"),
    "phon": ("sound", "Greek"),
    "graph": ("write", "Greek"),
    "gram": ("write, record", "Greek"),
    "log": ("word, study", "Greek"),
    "logy": ("study of", "Greek"),
    "bio": ("life", "Greek"),
    "geo": ("earth", "Greek"),
    "chron": ("time", "Greek"),
    "tele": ("far", "Greek"),
    "micro": ("small", "Greek"),
    "macro": ("large", "Greek"),
    "morph": ("form, shape", "Greek"),
    "path": ("feeling, disease", "Greek"),
    "phil": ("love", "Greek"),
    "phob": ("fear", "Greek"),
    "psych": ("mind", "Greek"),
    "soph": ("wisdom", "Greek"),
    "theo": ("god", "Greek"),
}


ANALYSIS_PROMPT = '''You are a morphological analysis specialist.

Analyze the following words and provide their morpheme breakdown.

For each word, identify:
1. The ROOT morpheme (the core meaning-carrying part)
2. Any PREFIXES
3. Any SUFFIXES
4. Syllable breakdown
5. Difficulty score (1-10, where 1=common/easy, 10=rare/challenging)

Return JSON array:
```json
[
  {
    "word": "unpredictable",
    "root": "dict",
    "morphemes": [
      {"text": "un", "type": "prefix", "meaning": "not", "origin": "Germanic"},
      {"text": "pre", "type": "prefix", "meaning": "before", "origin": "Latin"},
      {"text": "dict", "type": "root", "meaning": "say, speak", "origin": "Latin"},
      {"text": "able", "type": "suffix", "meaning": "capable of", "origin": "Latin"}
    ],
    "syllables": ["un", "pre", "dict", "a", "ble"],
    "difficulty": 6
  }
]
```

Words to analyze:
'''


class LexicalAnalyzer:
    """Analyzes vocabulary in documents to create a lexical map."""

    def __init__(
        self,
        model: Optional[str] = None,
        use_llm: bool = True,
    ) -> None:
        """Initialize the lexical analyzer.

        Args:
            model: LLM model to use for morpheme analysis
            use_llm: Whether to use LLM for analysis (vs local heuristics only)
        """
        settings = get_settings()
        self.model = model or settings.default_model
        self.use_llm = use_llm

    def extract_words(self, text: str, min_syllables: int = 2) -> list[str]:
        """Extract multisyllabic words from text.

        Args:
            text: The text to analyze
            min_syllables: Minimum syllables to include (default 2)

        Returns:
            List of unique words meeting criteria
        """
        # Remove formatting markers
        clean_text = re.sub(r"\*+", "", text)  # Remove bold/italic markers
        clean_text = re.sub(r"·", "", clean_text)  # Remove syllable dots
        clean_text = re.sub(r"\[Decoder Check:.*?\]", "", clean_text)  # Remove traps

        # Extract words (letters and apostrophes only)
        words = re.findall(r"[a-zA-Z']+", clean_text)

        # Filter and deduplicate
        seen = set()
        result = []
        for word in words:
            word_lower = word.lower()
            if word_lower not in seen and self._estimate_syllables(word) >= min_syllables:
                seen.add(word_lower)
                result.append(word)

        return result

    def _estimate_syllables(self, word: str) -> int:
        """Estimate syllable count using vowel groups.

        This is a heuristic - not 100% accurate but good enough for filtering.
        """
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

        # Adjust for -le endings (bottle, simple)
        if word.endswith("le") and len(word) > 2 and word[-3] not in "aeiouy":
            count += 1

        return max(1, count)

    def _analyze_word_locally(self, word: str) -> WordEntry:
        """Analyze a word using local morpheme dictionaries.

        This provides fast analysis without LLM calls.
        """
        word_lower = word.lower()
        morphemes: list[MorphemeInfo] = []
        root = ""
        remaining = word_lower

        # Check prefixes
        for prefix, (meaning, origin) in COMMON_PREFIXES.items():
            if remaining.startswith(prefix) and len(remaining) > len(prefix) + 2:
                morphemes.append(MorphemeInfo(
                    text=prefix,
                    meaning=meaning,
                    origin=origin,
                    morpheme_type="prefix",
                ))
                remaining = remaining[len(prefix):]

        # Check suffixes (save for later)
        suffix_morphemes: list[MorphemeInfo] = []
        for suffix, (meaning, origin) in COMMON_SUFFIXES.items():
            if remaining.endswith(suffix) and len(remaining) > len(suffix) + 2:
                suffix_morphemes.insert(0, MorphemeInfo(
                    text=suffix,
                    meaning=meaning,
                    origin=origin,
                    morpheme_type="suffix",
                ))
                remaining = remaining[:-len(suffix)]
                break  # Only one suffix at a time

        # Check for known roots
        for root_text, (meaning, origin) in COMMON_ROOTS.items():
            if root_text in remaining:
                root = root_text
                morphemes.append(MorphemeInfo(
                    text=root_text,
                    meaning=meaning,
                    origin=origin,
                    morpheme_type="root",
                ))
                break

        # If no known root found, use remaining as root
        if not root and remaining:
            root = remaining
            morphemes.append(MorphemeInfo(
                text=remaining,
                meaning="",
                origin="",
                morpheme_type="root",
            ))

        # Add suffixes
        morphemes.extend(suffix_morphemes)

        # Estimate syllables
        syllables = self._split_syllables(word)

        # Estimate difficulty
        difficulty = self._estimate_difficulty(word, morphemes)

        return WordEntry(
            word=word,
            root=root,
            morphemes=morphemes,
            syllables=syllables,
            difficulty_score=difficulty,
        )

    def _split_syllables(self, word: str) -> list[str]:
        """Split word into syllables using basic rules.

        This is a simplified syllabification - LLM provides better results.
        """
        word = word.lower()
        syllables = []
        current = ""

        i = 0
        while i < len(word):
            current += word[i]
            is_vowel = word[i] in "aeiouy"

            # Check if we should break here
            if is_vowel and i + 1 < len(word):
                next_char = word[i + 1]
                # VCV pattern: break before consonant (o-pen)
                if next_char not in "aeiouy":
                    # Check for consonant clusters
                    if i + 2 < len(word) and word[i + 2] not in "aeiouy":
                        # VCCV: break between consonants (hap-py)
                        current += next_char
                        syllables.append(current)
                        current = ""
                        i += 1
                    else:
                        syllables.append(current)
                        current = ""

            i += 1

        if current:
            if syllables:
                # Merge short endings
                if len(current) <= 2 and current not in ["ed", "er", "ly"]:
                    syllables[-1] += current
                else:
                    syllables.append(current)
            else:
                syllables.append(current)

        return syllables if syllables else [word]

    def _estimate_difficulty(self, word: str, morphemes: list[MorphemeInfo]) -> int:
        """Estimate word difficulty on 1-10 scale."""
        difficulty = 5  # Base difficulty

        # Length factor
        if len(word) > 10:
            difficulty += 1
        if len(word) > 14:
            difficulty += 1

        # Morpheme complexity
        if len(morphemes) > 3:
            difficulty += 1

        # Greek/Latin origin tends to be harder
        for m in morphemes:
            if m.origin == "Greek":
                difficulty += 0.5
            elif m.origin == "Latin":
                difficulty += 0.3

        # Unknown morphemes are harder
        unknown_count = sum(1 for m in morphemes if not m.meaning)
        difficulty += unknown_count * 0.5

        return min(10, max(1, int(difficulty)))

    def _analyze_words_with_llm(self, words: list[str]) -> list[WordEntry]:
        """Use LLM to analyze words for deeper morpheme understanding."""
        if not words:
            return []

        prompt = ANALYSIS_PROMPT + "\n".join(words[:50])  # Limit batch size

        try:
            response = completion(
                model=self.model,
                messages=[
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                max_tokens=4000,
            )
            content = response.choices[0].message.content
            if content:
                return self._parse_llm_analysis(content, words)
        except Exception:
            pass

        # Fall back to local analysis
        return [self._analyze_word_locally(w) for w in words]

    def _parse_llm_analysis(self, response: str, original_words: list[str]) -> list[WordEntry]:
        """Parse LLM morpheme analysis response."""
        import json

        # Clean response
        response = response.strip()
        if response.startswith("```"):
            response = re.sub(r"^```(?:json)?\n?", "", response)
            response = re.sub(r"\n?```$", "", response)

        entries = []
        try:
            data = json.loads(response)
            if not isinstance(data, list):
                data = [data]

            for item in data:
                morphemes = []
                for m in item.get("morphemes", []):
                    morphemes.append(MorphemeInfo(
                        text=m.get("text", ""),
                        meaning=m.get("meaning", ""),
                        origin=m.get("origin", ""),
                        morpheme_type=m.get("type", "root"),
                    ))

                entry = WordEntry(
                    word=item.get("word", ""),
                    root=item.get("root", ""),
                    morphemes=morphemes,
                    syllables=item.get("syllables", []),
                    difficulty_score=item.get("difficulty", 5),
                )
                entries.append(entry)

        except json.JSONDecodeError:
            # Fall back to local analysis for unparseable responses
            entries = [self._analyze_word_locally(w) for w in original_words]

        # Fill in any missing words from original list
        analyzed_words = {e.word.lower() for e in entries}
        for word in original_words:
            if word.lower() not in analyzed_words:
                entries.append(self._analyze_word_locally(word))

        return entries

    def analyze_document(self, doc: FormattedDocument) -> LexicalMap:
        """Analyze all vocabulary in a document.

        Args:
            doc: The formatted document to analyze

        Returns:
            LexicalMap with all vocabulary analysis
        """
        # Extract text from document
        text = doc.plain_text

        # Extract multisyllabic words
        words = self.extract_words(text, min_syllables=2)

        # Analyze words
        if self.use_llm and len(words) > 0:
            entries = self._analyze_words_with_llm(words)
        else:
            entries = [self._analyze_word_locally(w) for w in words]

        # Build lexical map
        lexical_map = LexicalMap()

        # Track first occurrences
        text_lower = text.lower()
        for entry in entries:
            word_lower = entry.word.lower()
            # Find paragraph index of first occurrence
            for i, block in enumerate(doc.blocks):
                if word_lower in block.plain_text.lower():
                    entry.first_occurrence = i
                    break
            lexical_map.add_word(entry)

        # Build morpheme families
        lexical_map.families = lexical_map.get_root_families()

        return lexical_map

    def enhance_document(self, doc: FormattedDocument) -> FormattedDocument:
        """Add lexical analysis to a document.

        Args:
            doc: The document to enhance

        Returns:
            Document with vocabulary metadata populated
        """
        lexical_map = self.analyze_document(doc)

        if doc.vocabulary is None:
            doc.vocabulary = VocabularyMetadata()

        doc.vocabulary.lexical_map = lexical_map

        # Select pre-reading words (most difficult, first occurrences)
        difficult_words = sorted(
            lexical_map.words.values(),
            key=lambda w: (-w.difficulty_score, w.first_occurrence),
        )[:10]
        doc.vocabulary.pre_reading_words = difficult_words

        return doc
