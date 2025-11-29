"""Tests for the CLI interface."""

import pytest
from pathlib import Path
from unittest.mock import patch, Mock

from typer.testing import CliRunner

from anchor_text.cli import app, generate_output_path


runner = CliRunner()


class TestGenerateOutputPath:
    """Tests for output path generation."""

    def test_adds_anchor_suffix(self):
        """Test that -anchor suffix is added to filename."""
        input_path = Path("/path/to/document.pdf")
        output = generate_output_path(input_path)

        assert output.name == "document-anchor.pdf"
        assert output.parent == input_path.parent

    def test_preserves_extension(self):
        """Test that file extension is preserved."""
        for ext in [".txt", ".pdf", ".docx", ".odt", ".rtf", ".epub"]:
            input_path = Path(f"/path/to/file{ext}")
            output = generate_output_path(input_path)

            assert output.suffix == ext

    def test_handles_spaces_in_filename(self):
        """Test handling of spaces in filename."""
        input_path = Path("/path/to/my document.pdf")
        output = generate_output_path(input_path)

        assert output.name == "my document-anchor.pdf"

    def test_custom_output_directory(self):
        """Test specifying custom output directory."""
        input_path = Path("/path/to/document.pdf")
        output_dir = Path("/custom/output")
        output = generate_output_path(input_path, output_dir)

        assert output.parent == output_dir
        assert output.name == "document-anchor.pdf"


class TestCLI:
    """Tests for CLI commands."""

    def test_version_flag(self):
        """Test --version flag."""
        result = runner.invoke(app, ["--version"])

        assert result.exit_code == 0
        assert "Anchor Text" in result.stdout

    def test_help_flag(self):
        """Test --help flag."""
        result = runner.invoke(app, ["--help"])

        assert result.exit_code == 0
        assert "Literacy Bridge Protocol" in result.stdout

    def test_missing_file_error(self, tmp_path: Path):
        """Test error when file doesn't exist."""
        fake_path = tmp_path / "nonexistent.txt"
        result = runner.invoke(app, [str(fake_path)])

        assert result.exit_code != 0

    def test_unsupported_format_warning(self, tmp_path: Path):
        """Test warning for unsupported file formats."""
        # Create an unsupported file type
        unsupported = tmp_path / "file.xyz"
        unsupported.write_text("content")

        result = runner.invoke(app, [str(unsupported)])

        # Should fail or warn about unsupported format
        assert result.exit_code != 0 or "unsupported" in result.stdout.lower()

    @patch("anchor_text.cli.TextTransformer")
    def test_single_file_processing(
        self, mock_transformer_class: Mock, tmp_path: Path
    ):
        """Test processing a single file."""
        # Setup
        input_file = tmp_path / "test.txt"
        input_file.write_text("Hello world")

        mock_transformer = Mock()
        mock_transformer_class.return_value = mock_transformer

        # Run
        result = runner.invoke(app, [str(input_file)])

        # Verify transformer was called
        mock_transformer.transform_file.assert_called_once()
        call_args = mock_transformer.transform_file.call_args
        assert call_args[0][0] == input_file

    @patch("anchor_text.cli.TextTransformer")
    def test_folder_processing(
        self, mock_transformer_class: Mock, tmp_path: Path
    ):
        """Test processing a folder of files."""
        # Create test files
        (tmp_path / "file1.txt").write_text("Content 1")
        (tmp_path / "file2.txt").write_text("Content 2")
        (tmp_path / "ignored.xyz").write_text("Ignored")

        mock_transformer = Mock()
        mock_transformer_class.return_value = mock_transformer

        # Run
        result = runner.invoke(app, [str(tmp_path)])

        # Should process txt files but not xyz
        assert mock_transformer.transform_file.call_count == 2

    @patch("anchor_text.cli.TextTransformer")
    def test_skips_already_processed_files(
        self, mock_transformer_class: Mock, tmp_path: Path
    ):
        """Test that files with -anchor suffix are skipped."""
        # Create files including an already-processed one
        (tmp_path / "original.txt").write_text("Original")
        (tmp_path / "original-anchor.txt").write_text("Already processed")

        mock_transformer = Mock()
        mock_transformer_class.return_value = mock_transformer

        # Run
        result = runner.invoke(app, [str(tmp_path)])

        # Should only process original, not the -anchor file
        assert mock_transformer.transform_file.call_count == 1

    def test_model_option(self, tmp_path: Path):
        """Test --model option is passed through."""
        input_file = tmp_path / "test.txt"
        input_file.write_text("Hello")

        with patch("anchor_text.cli.TextTransformer") as mock_class:
            mock_transformer = Mock()
            mock_class.return_value = mock_transformer

            runner.invoke(
                app, [str(input_file), "--model", "openai/gpt-4o"]
            )

            # Check model was passed to transformer
            mock_class.assert_called_once_with(model="openai/gpt-4o")
