"""LLM client wrapper using LiteLLM for multi-provider support."""

import os
from typing import Optional

from litellm import completion
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from anchor_text.config import get_settings
from anchor_text.formatting.ir import ScaffoldLevel
from anchor_text.llm.prompts import get_system_prompt


class LLMError(Exception):
    """Error communicating with LLM provider."""

    pass


class ValidationError(Exception):
    """AI output failed validation."""

    pass


class LLMClient:
    """Unified LLM client using LiteLLM for provider-agnostic API calls."""

    def __init__(
        self,
        model: Optional[str] = None,
        api_base: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: int = 4096,
    ) -> None:
        """Initialize the LLM client.

        Args:
            model: LiteLLM model string (e.g., "gemini/gemini-3-pro-preview")
            api_base: Optional API base URL (for local LLMs)
            temperature: Sampling temperature (lower = more deterministic)
            max_tokens: Maximum tokens in response
        """
        settings = get_settings()
        self.model = model or settings.default_model
        self.api_base = api_base
        self.temperature = temperature or settings.llm_temperature
        self.max_tokens = max_tokens
        self.max_retries = settings.max_retries

        # Ensure API keys are set in environment for LiteLLM
        self._setup_api_keys(settings)

    def _setup_api_keys(self, settings) -> None:
        """Ensure API keys are available in environment for LiteLLM."""
        # LiteLLM expects GEMINI_API_KEY for Google AI Studio
        # Also accept GOOGLE_API_KEY as fallback
        if settings.gemini_api_key:
            os.environ["GEMINI_API_KEY"] = settings.gemini_api_key
        elif settings.google_api_key:
            os.environ["GEMINI_API_KEY"] = settings.google_api_key

        if settings.openai_api_key:
            os.environ["OPENAI_API_KEY"] = settings.openai_api_key

        if settings.anthropic_api_key:
            os.environ["ANTHROPIC_API_KEY"] = settings.anthropic_api_key

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((LLMError,)),
        reraise=True,
    )
    def _call_llm(self, text: str, system_prompt: str) -> str:
        """Make an LLM API call with retry logic."""
        try:
            response = completion(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": text},
                ],
                api_base=self.api_base,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )
            content = response.choices[0].message.content
            if content is None:
                raise LLMError("LLM returned empty response")
            return content
        except Exception as e:
            if "rate_limit" in str(e).lower():
                raise LLMError(f"Rate limited: {e}") from e
            elif "api" in str(e).lower() or "connection" in str(e).lower():
                raise LLMError(f"API error: {e}") from e
            raise

    def transform_text(
        self,
        text: str,
        is_continuation: bool = False,
        is_final: bool = True,
        level: int = ScaffoldLevel.MAX,
    ) -> str:
        """Transform text using the Literacy Bridge Protocol.

        Args:
            text: The text to transform
            is_continuation: Whether this is a middle chunk
            is_final: Whether this is the last chunk
            level: Scaffolding level (1-5, default 1 = MAX support)

        Returns:
            Transformed text with protocol formatting applied
        """
        system_prompt = get_system_prompt(is_continuation, is_final, level)
        return self._call_llm(text, system_prompt)

    def transform_with_validation(
        self,
        text: str,
        is_continuation: bool = False,
        is_final: bool = True,
        level: int = ScaffoldLevel.MAX,
    ) -> str:
        """Transform text with validation and auto-retry on failure.

        Args:
            text: The text to transform
            is_continuation: Whether this is a middle chunk
            is_final: Whether this is the last chunk
            level: Scaffolding level (1-5, default 1 = MAX support)

        Returns:
            Validated transformed text

        Raises:
            ValidationError: If validation fails after max retries
        """
        # Validation requirements vary by level
        expect_bold = level <= ScaffoldLevel.MED  # Levels 1-3 have bold
        expect_italic = level <= ScaffoldLevel.MED  # Levels 1-3 have italic
        expect_dots = level == ScaffoldLevel.MAX  # Only level 1 has dots
        expect_trap = level <= ScaffoldLevel.LOW  # Levels 1-4 have traps

        for attempt in range(self.max_retries):
            result = self.transform_text(text, is_continuation, is_final, level)

            # Use level-appropriate validation
            is_valid, issues = validate_transformation(
                result,
                expect_decoder_trap=expect_trap,
                expect_bold=expect_bold,
                expect_italic=expect_italic,
                expect_syllable_dots=expect_dots,
            )

            if is_valid:
                return result

            if attempt < self.max_retries - 1:
                # Retry with a reminder prompt
                reminder = (
                    f"\n\nIMPORTANT: Your previous response was missing: "
                    f"{', '.join(issues)}. Please ensure ALL rules are applied."
                )
                result = self._call_llm(
                    text + reminder,
                    get_system_prompt(is_continuation, is_final, level),
                )
                is_valid, issues = validate_transformation(
                    result,
                    expect_decoder_trap=expect_trap,
                    expect_bold=expect_bold,
                    expect_italic=expect_italic,
                    expect_syllable_dots=expect_dots,
                )
                if is_valid:
                    return result

        # Return anyway with warning (don't fail completely)
        return result


def validate_transformation(
    output: str,
    expect_decoder_trap: bool = True,
    expect_bold: bool = True,
    expect_italic: bool = True,
    expect_syllable_dots: bool = True,
) -> tuple[bool, list[str]]:
    """Validate that AI output contains required Literacy Bridge elements.

    Args:
        output: The AI's transformed text
        expect_decoder_trap: Whether to require the Decoder's Trap
        expect_bold: Whether to require bold formatting
        expect_italic: Whether to require italic formatting
        expect_syllable_dots: Whether to require syllable dots

    Returns:
        Tuple of (is_valid, list_of_issues)
    """
    issues: list[str] = []

    # Check for bold markers (root anchoring / syntactic spine subjects)
    if expect_bold and "**" not in output:
        issues.append("bold formatting (root anchoring/subjects)")

    # Check for italic markers (syntactic spine verbs)
    # Need to check for single * that's not part of **
    if expect_italic:
        has_italic = False
        i = 0
        while i < len(output):
            if output[i] == "*":
                if i + 1 < len(output) and output[i + 1] == "*":
                    # This is bold, skip
                    i += 2
                    continue
                else:
                    has_italic = True
                    break
            i += 1

        if not has_italic:
            issues.append("italic formatting (verbs)")

    # Check for middle dots (syllable breaking)
    if expect_syllable_dots and "·" not in output:
        issues.append("syllable breaks (middle dots)")

    # Check for Decoder's Trap
    if expect_decoder_trap:
        decoder_markers = ["[Decoder Check:", "DECODER'S TRAP:", "Decoder's Trap:"]
        has_trap = any(marker.lower() in output.lower() for marker in decoder_markers)
        if not has_trap:
            issues.append("Decoder's Trap question")

    return len(issues) == 0, issues
