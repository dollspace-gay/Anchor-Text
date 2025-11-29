"""Enhanced Decoder Traps generator.

This module implements System 3 - generating decoder traps with lookalike
word distractors to catch readers who guess based on word shape rather
than properly decoding.
"""

import json
import re
from typing import Optional

from litellm import completion

from anchor_text.config import get_settings
from anchor_text.formatting.ir import (
    DecoderTrap,
    TrapOption,
    FormattedDocument,
    VocabularyMetadata,
)


TRAP_GENERATOR_PROMPT = '''You are a reading assessment specialist creating decoder traps for literacy rehabilitation.

Your task: Generate enhanced multiple-choice decoder traps that catch readers who GUESS words instead of DECODING them.

## WHAT MAKES A GOOD TRAP

Three-cueing readers guess words based on:
1. First letter + word length
2. Word shape (ascenders/descenders)
3. Context clues

A good trap includes "lookalike" distractors that:
- Start with the same letter
- Have similar length
- Have similar visual shape
- Would make sense in context (but are WRONG)

## INPUT FORMAT

You will receive paragraphs with target words marked. For each paragraph, generate a trap.

## OUTPUT FORMAT

Return a JSON array of trap objects. Each trap:
```json
{
  "paragraph_index": 0,
  "question": "What did the scientists do about the results?",
  "target_word": "hypothesized",
  "correct_answer": "hypothesized",
  "distractors": [
    {"word": "hospitalized", "is_lookalike": true},
    {"word": "harmonized", "is_lookalike": true},
    {"word": "analyzed", "is_lookalike": false}
  ],
  "explanation": "The word 'hypothesized' means to propose a theory. It starts with 'hypo-' (under/below) not 'hospi-' (guest/host)."
}
```

## LOOKALIKE SELECTION GUIDELINES

For a target word, find lookalikes that share:
- Same first 2-3 letters (hypothesis → hospitalized)
- Same general shape (tall letters in same positions)
- Similar syllable count
- Same ending pattern when possible (-tion, -ment, -ly, etc.)

Common lookalike pairs:
- predict/protect, through/though/thorough
- hypothesis/hospitalize, beautiful/bountiful
- consecutive/conservative, consider/consumer

Include 2-3 lookalikes and 1 context-plausible non-lookalike per trap.

## IMPORTANT
- Output ONLY valid JSON, no markdown code blocks
- Each paragraph gets exactly one trap
- Questions should require READING the exact word, not guessing from context
'''


class TrapGenerator:
    """Generates enhanced decoder traps with lookalike distractors."""

    def __init__(
        self,
        model: Optional[str] = None,
        temperature: float = 0.4,
    ) -> None:
        """Initialize the trap generator.

        Args:
            model: LLM model to use (defaults to settings)
            temperature: Sampling temperature (slightly higher for creativity)
        """
        settings = get_settings()
        self.model = model or settings.default_model
        self.temperature = temperature

    def _extract_target_words(self, doc: FormattedDocument) -> list[dict]:
        """Extract target words from decoder trap blocks.

        Returns list of {paragraph_index, paragraph_text, existing_question}
        """
        targets = []
        paragraph_index = 0

        for i, block in enumerate(doc.blocks):
            if block.is_decoder_trap:
                # Extract the question text
                question_text = block.plain_text
                # Try to find the previous paragraph
                if paragraph_index > 0:
                    # Find the actual paragraph (skip other traps)
                    para_blocks = [b for b in doc.blocks[:i] if not b.is_decoder_trap]
                    if para_blocks:
                        last_para = para_blocks[-1].plain_text
                        targets.append({
                            "paragraph_index": len(para_blocks) - 1,
                            "paragraph_text": last_para,
                            "existing_question": question_text,
                        })
            else:
                paragraph_index += 1

        return targets

    def _build_prompt(self, targets: list[dict]) -> str:
        """Build the prompt for the LLM with paragraph/question pairs."""
        parts = ["Generate enhanced decoder traps for these paragraphs:\n"]

        for i, target in enumerate(targets):
            parts.append(f"\n--- Paragraph {i} ---")
            parts.append(target["paragraph_text"])
            parts.append(f"\nExisting question: {target['existing_question']}")

        parts.append("\n\nReturn JSON array of enhanced traps.")
        return "\n".join(parts)

    def _parse_response(self, response: str, targets: list[dict]) -> list[DecoderTrap]:
        """Parse LLM response into DecoderTrap objects."""
        traps = []

        # Clean response - remove markdown code blocks if present
        response = response.strip()
        if response.startswith("```"):
            response = re.sub(r"^```(?:json)?\n?", "", response)
            response = re.sub(r"\n?```$", "", response)

        try:
            data = json.loads(response)
        except json.JSONDecodeError:
            # Fall back to simple traps if JSON parsing fails
            return self._fallback_simple_traps(targets)

        if not isinstance(data, list):
            data = [data]

        for item in data:
            options = []

            # Add correct answer
            options.append(TrapOption(
                text=item.get("correct_answer", item.get("target_word", "")),
                is_correct=True,
                is_lookalike=False,
            ))

            # Add distractors
            for dist in item.get("distractors", []):
                if isinstance(dist, dict):
                    options.append(TrapOption(
                        text=dist.get("word", ""),
                        is_correct=False,
                        is_lookalike=dist.get("is_lookalike", False),
                    ))
                elif isinstance(dist, str):
                    options.append(TrapOption(
                        text=dist,
                        is_correct=False,
                        is_lookalike=False,
                    ))

            trap = DecoderTrap(
                question=item.get("question", ""),
                target_word=item.get("target_word", ""),
                options=options,
                paragraph_index=item.get("paragraph_index", 0),
                explanation=item.get("explanation", ""),
            )
            traps.append(trap)

        return traps

    def _fallback_simple_traps(self, targets: list[dict]) -> list[DecoderTrap]:
        """Create simple traps when LLM response can't be parsed."""
        traps = []
        for i, target in enumerate(targets):
            # Extract question from existing decoder check
            question = target["existing_question"]
            question = re.sub(r"\[Decoder Check:\s*", "", question)
            question = re.sub(r"\]$", "", question)

            trap = DecoderTrap(
                question=question,
                target_word="",
                options=[],
                paragraph_index=i,
                explanation="",
            )
            traps.append(trap)

        return traps

    def generate_traps(self, doc: FormattedDocument) -> list[DecoderTrap]:
        """Generate enhanced decoder traps for a document.

        Args:
            doc: The formatted document with basic decoder traps

        Returns:
            List of enhanced DecoderTrap objects
        """
        targets = self._extract_target_words(doc)

        if not targets:
            return []

        prompt = self._build_prompt(targets)

        try:
            response = completion(
                model=self.model,
                messages=[
                    {"role": "system", "content": TRAP_GENERATOR_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                temperature=self.temperature,
                max_tokens=2000,
            )
            content = response.choices[0].message.content
            if content:
                return self._parse_response(content, targets)
        except Exception:
            # On error, fall back to simple traps
            pass

        return self._fallback_simple_traps(targets)

    def enhance_document(self, doc: FormattedDocument) -> FormattedDocument:
        """Add enhanced traps to a document's vocabulary metadata.

        Args:
            doc: The formatted document to enhance

        Returns:
            The same document with vocabulary.traps populated
        """
        traps = self.generate_traps(doc)

        if doc.vocabulary is None:
            doc.vocabulary = VocabularyMetadata()

        doc.vocabulary.traps = traps
        return doc


def generate_lookalikes(word: str, count: int = 3) -> list[str]:
    """Generate lookalike words for a target word.

    This is a simple heuristic-based generator for common patterns.
    The LLM-based approach in TrapGenerator is more sophisticated.

    Args:
        word: The target word
        count: Number of lookalikes to generate

    Returns:
        List of lookalike words
    """
    # Common prefix substitutions
    prefix_subs = {
        "pre": ["pro", "per", "pri"],
        "con": ["com", "can", "cen"],
        "dis": ["des", "das", "dys"],
        "un": ["in", "on", "an"],
        "hypo": ["hyper", "hospi", "hippo"],
        "inter": ["intra", "intro", "enter"],
        "trans": ["trance", "train", "tract"],
        "super": ["supper", "supra", "souper"],
    }

    # Common suffix substitutions
    suffix_subs = {
        "tion": ["sion", "cion", "tian"],
        "ment": ["mint", "meant", "mont"],
        "able": ["ible", "uble", "ably"],
        "ness": ["ness", "niss", "nous"],
        "ize": ["ise", "aze", "ice"],
    }

    lookalikes = []

    word_lower = word.lower()

    # Try prefix substitution
    for prefix, subs in prefix_subs.items():
        if word_lower.startswith(prefix):
            for sub in subs[:count]:
                lookalike = sub + word[len(prefix):]
                if lookalike.lower() != word_lower:
                    lookalikes.append(lookalike)
                if len(lookalikes) >= count:
                    return lookalikes

    # Try suffix substitution
    for suffix, subs in suffix_subs.items():
        if word_lower.endswith(suffix):
            for sub in subs[:count]:
                lookalike = word[:-len(suffix)] + sub
                if lookalike.lower() != word_lower:
                    lookalikes.append(lookalike)
                if len(lookalikes) >= count:
                    return lookalikes

    # Fallback: letter substitution at position 2-3
    if len(word) > 3 and len(lookalikes) < count:
        # Swap similar-looking letters
        similar_letters = {
            'a': ['o', 'e'], 'e': ['a', 'o'], 'i': ['l', 'j'],
            'o': ['a', 'e'], 'u': ['v', 'n'], 'n': ['m', 'u'],
            'm': ['n', 'w'], 'b': ['d', 'p'], 'd': ['b', 'p'],
            'p': ['b', 'd', 'q'], 'q': ['p', 'g'],
        }
        for pos in [2, 3, 1]:
            if pos < len(word):
                char = word[pos].lower()
                if char in similar_letters:
                    for replacement in similar_letters[char]:
                        lookalike = word[:pos] + replacement + word[pos+1:]
                        if lookalike.lower() != word_lower:
                            lookalikes.append(lookalike)
                        if len(lookalikes) >= count:
                            return lookalikes

    return lookalikes[:count]
