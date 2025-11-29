"""Main text transformation orchestrator."""

from pathlib import Path
from typing import Optional

from anchor_text.config import get_settings
from anchor_text.formats import get_handler, SUPPORTED_EXTENSIONS
from anchor_text.formatting.ir import FormattedDocument, ImageRef
from anchor_text.formatting.parser import MarkdownParser
from anchor_text.llm.client import LLMClient
from anchor_text.llm.chunker import DocumentChunker


class TransformationError(Exception):
    """Error during text transformation."""

    pass


class TextTransformer:
    """Orchestrates the text transformation pipeline.

    Pipeline:
    1. Read input file (extract text and images)
    2. Chunk text if needed (for large documents)
    3. Transform via LLM with Literacy Bridge Protocol
    4. Parse AI markdown output to IR
    5. Write to output file in same format
    """

    def __init__(
        self,
        model: Optional[str] = None,
        api_base: Optional[str] = None,
    ) -> None:
        """Initialize the transformer.

        Args:
            model: LiteLLM model string
            api_base: Optional API base URL for local LLMs
        """
        settings = get_settings()
        self.model = model or settings.default_model
        self.api_base = api_base

        self.llm_client = LLMClient(model=self.model, api_base=self.api_base)
        self.chunker = DocumentChunker()
        self.parser = MarkdownParser()

    def transform_file(
        self,
        input_path: Path,
        output_path: Path,
    ) -> FormattedDocument:
        """Transform a document file.

        Args:
            input_path: Path to input document
            output_path: Path for output document

        Returns:
            The FormattedDocument that was written

        Raises:
            TransformationError: If transformation fails
        """
        # Validate input
        if not input_path.exists():
            raise TransformationError(f"Input file not found: {input_path}")

        ext = input_path.suffix.lower()
        if ext not in SUPPORTED_EXTENSIONS:
            raise TransformationError(
                f"Unsupported format: {ext}. "
                f"Supported: {', '.join(SUPPORTED_EXTENSIONS)}"
            )

        # Get handlers
        handler_class = get_handler(ext)
        handler = handler_class()

        # Read input
        text, images = handler.read_with_images(input_path)

        if not text.strip():
            raise TransformationError("Input file contains no text")

        # Transform text
        transformed_text = self._transform_text(text)

        # Parse to IR
        document = self.parser.parse(
            transformed_text,
            images=images,
            metadata={"source": str(input_path)},
        )

        # Write output
        output_handler_class = get_handler(output_path.suffix.lower())
        output_handler = output_handler_class()
        output_handler.write(document, output_path)

        return document

    def _transform_text(self, text: str) -> str:
        """Transform text via LLM, handling chunking if needed.

        Args:
            text: The plain text to transform

        Returns:
            Transformed text with Literacy Bridge formatting
        """
        if not self.chunker.needs_chunking(text):
            # Single chunk - simple case
            return self.llm_client.transform_with_validation(
                text, is_continuation=False, is_final=True
            )

        # Multi-chunk processing
        transformed_parts: list[str] = []

        for chunk_text, is_first, is_last in self.chunker.chunk_text(text):
            transformed = self.llm_client.transform_with_validation(
                chunk_text,
                is_continuation=not is_first,
                is_final=is_last,
            )
            transformed_parts.append(transformed)

        # Join chunks (remove any duplicate overlap content)
        return self._merge_chunks(transformed_parts)

    def _merge_chunks(self, chunks: list[str]) -> str:
        """Merge transformed chunks, handling overlaps.

        The chunker adds overlap between chunks for context.
        We need to remove duplicated content in the merged output.
        """
        if len(chunks) <= 1:
            return chunks[0] if chunks else ""

        # Simple merge - just join with paragraph break
        # More sophisticated deduplication would compare end of chunk N
        # with start of chunk N+1, but that's complex with formatted text
        return "\n\n".join(chunks)

    def transform_text_only(self, text: str) -> str:
        """Transform text without file I/O.

        Useful for testing or streaming applications.

        Args:
            text: Plain text to transform

        Returns:
            Transformed text with Literacy Bridge formatting
        """
        return self._transform_text(text)

    def transform_to_document(
        self,
        text: str,
        images: Optional[list[ImageRef]] = None,
    ) -> FormattedDocument:
        """Transform text and return as FormattedDocument.

        Args:
            text: Plain text to transform
            images: Optional images to include

        Returns:
            FormattedDocument with parsed content
        """
        transformed = self._transform_text(text)
        return self.parser.parse(transformed, images=images)
