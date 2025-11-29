"""Pytest fixtures for Anchor Text tests."""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch


@pytest.fixture
def sample_text() -> str:
    """Sample text for testing transformations."""
    return (
        "The quick brown fox jumps over the lazy dog. "
        "Philosophy is the study of fundamental questions about existence."
    )


@pytest.fixture
def sample_transformed_text() -> str:
    """Sample transformed text matching Literacy Bridge Protocol."""
    return '''**The quick brown fox** *jumps* over **the lazy dog**.

**Phi·los·o·phy** *is* the study of **fun·da·men·tal** questions about ex·is·tence.

[Decoder Check: What three-syllable word describes questions that are basic and essential?]'''


@pytest.fixture
def mock_llm_response(sample_transformed_text: str) -> str:
    """Mock LLM response."""
    return sample_transformed_text


@pytest.fixture
def mock_llm_client(mock_llm_response: str):
    """Create a mock LLM client for testing without API calls."""
    with patch("anchor_text.llm.client.completion") as mock_completion:
        mock_completion.return_value = Mock(
            choices=[Mock(message=Mock(content=mock_llm_response))]
        )
        yield mock_completion


@pytest.fixture
def tmp_text_file(tmp_path: Path, sample_text: str) -> Path:
    """Create a temporary text file for testing."""
    file_path = tmp_path / "test.txt"
    file_path.write_text(sample_text, encoding="utf-8")
    return file_path


@pytest.fixture
def tmp_output_path(tmp_path: Path) -> Path:
    """Get a temporary output path."""
    return tmp_path / "output.txt"
