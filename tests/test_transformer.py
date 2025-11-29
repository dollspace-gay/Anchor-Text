"""Tests for the text transformer."""

import pytest
from pathlib import Path
from unittest.mock import patch, Mock

from anchor_text.core.transformer import TextTransformer, TransformationError


class TestTextTransformer:
    """Tests for the TextTransformer class."""

    @pytest.fixture
    def mock_llm(self, sample_transformed_text: str):
        """Mock the LLM completion call."""
        with patch("anchor_text.llm.client.completion") as mock:
            mock.return_value = Mock(
                choices=[Mock(message=Mock(content=sample_transformed_text))]
            )
            yield mock

    def test_transform_file_txt(
        self,
        mock_llm: Mock,
        tmp_path: Path,
        sample_text: str,
        sample_transformed_text: str,
    ):
        """Test transforming a text file."""
        # Create input file
        input_file = tmp_path / "input.txt"
        input_file.write_text(sample_text)

        output_file = tmp_path / "output.txt"

        # Transform
        transformer = TextTransformer()
        doc = transformer.transform_file(input_file, output_file)

        # Verify output was created
        assert output_file.exists()

        # Verify document has content
        assert len(doc.blocks) > 0

    def test_transform_file_not_found(self, tmp_path: Path):
        """Test error when input file doesn't exist."""
        transformer = TextTransformer()

        with pytest.raises(TransformationError, match="not found"):
            transformer.transform_file(
                tmp_path / "nonexistent.txt",
                tmp_path / "output.txt",
            )

    def test_transform_unsupported_format(self, tmp_path: Path):
        """Test error for unsupported file format."""
        input_file = tmp_path / "file.xyz"
        input_file.write_text("content")

        transformer = TextTransformer()

        with pytest.raises(TransformationError, match="Unsupported"):
            transformer.transform_file(input_file, tmp_path / "output.xyz")

    def test_transform_empty_file(self, tmp_path: Path):
        """Test error for empty input file."""
        input_file = tmp_path / "empty.txt"
        input_file.write_text("")

        transformer = TextTransformer()

        with pytest.raises(TransformationError, match="no text"):
            transformer.transform_file(input_file, tmp_path / "output.txt")

    def test_transform_text_only(
        self, mock_llm: Mock, sample_text: str, sample_transformed_text: str
    ):
        """Test transforming text without file I/O."""
        transformer = TextTransformer()
        result = transformer.transform_text_only(sample_text)

        assert "**" in result  # Has bold
        assert "*" in result  # Has italic
        mock_llm.assert_called()

    def test_transform_to_document(
        self, mock_llm: Mock, sample_text: str
    ):
        """Test transforming text to FormattedDocument."""
        transformer = TextTransformer()
        doc = transformer.transform_to_document(sample_text)

        assert len(doc.blocks) > 0
        assert doc.has_decoder_trap

    def test_custom_model(self, mock_llm: Mock):
        """Test using a custom model."""
        transformer = TextTransformer(model="openai/gpt-4o")

        assert transformer.model == "openai/gpt-4o"

    def test_preserves_same_format(
        self, mock_llm: Mock, tmp_path: Path, sample_text: str
    ):
        """Test that output format matches input format."""
        for ext in [".txt"]:  # Only test txt for now (others need deps)
            input_file = tmp_path / f"input{ext}"
            input_file.write_text(sample_text)

            output_file = tmp_path / f"output{ext}"

            transformer = TextTransformer()
            transformer.transform_file(input_file, output_file)

            assert output_file.suffix == input_file.suffix
