"""Main text transformation orchestrator."""

from pathlib import Path
from typing import Optional

from anchor_text.config import get_settings
from anchor_text.formats import get_handler, SUPPORTED_EXTENSIONS
from anchor_text.formatting.ir import (
    FormattedDocument,
    ImageRef,
    ScaffoldLevel,
    VocabularyMetadata,
)
from anchor_text.formatting.parser import MarkdownParser
from anchor_text.llm.client import LLMClient
from anchor_text.llm.chunker import DocumentChunker
from anchor_text.llm.traps import TrapGenerator
from anchor_text.lexical.primer import PrimerGenerator
from anchor_text.lexical.analyzer import LexicalAnalyzer
from anchor_text.core.scaffolding import ScaffoldingContext, FadingProfile


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
    5. Optionally enhance with interactive traps (System 3)
    6. Write to output file in same format
    """

    def __init__(
        self,
        model: Optional[str] = None,
        api_base: Optional[str] = None,
        level: int = ScaffoldLevel.MAX,
        enhanced_traps: bool = False,
        pre_reading_primer: bool = False,
        adaptive: bool = False,
        fade_threshold: Optional[int] = None,
    ) -> None:
        """Initialize the transformer.

        Args:
            model: LiteLLM model string
            api_base: Optional API base URL for local LLMs
            level: Scaffolding level (1-5, default 1 = MAX support)
            enhanced_traps: Whether to generate enhanced decoder traps
            pre_reading_primer: Whether to generate pre-reading warm-up section
            adaptive: Whether to use adaptive scaffolding (fade support for repeated words)
            fade_threshold: Custom threshold for word mastery (default: 3 for adaptive)
        """
        settings = get_settings()
        self.model = model or settings.default_model
        self.api_base = api_base
        self.level = ScaffoldLevel.validate(level)
        self.enhanced_traps = enhanced_traps
        self.pre_reading_primer = pre_reading_primer
        self.adaptive = adaptive
        self.fade_threshold = fade_threshold

        self.llm_client = LLMClient(model=self.model, api_base=self.api_base)
        self.chunker = DocumentChunker()
        self.parser = MarkdownParser()

        # Always initialize lexical analyzer (decoupled from other components)
        self.lexical_analyzer = LexicalAnalyzer(model=self.model, use_llm=False)

        # Optional components that can use the lexical analysis
        self.trap_generator = TrapGenerator(model=self.model) if enhanced_traps else None
        self.primer_generator = PrimerGenerator(model=self.model, use_llm=False) if pre_reading_primer else None

        # Initialize scaffolding context for adaptive mode
        if adaptive:
            profile = FadingProfile.ADAPTIVE
            self.scaffold_context = ScaffoldingContext(
                profile=profile,
                threshold=fade_threshold,
            )
        else:
            self.scaffold_context = None

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
            metadata={"source": str(input_path), "scaffold_level": self.level},
        )

        # Add vocabulary metadata with scaffold level
        document.vocabulary = VocabularyMetadata(scaffold_level=self.level)

        # Always run lexical analysis (decoupled from primer/traps)
        lexical_map = self.lexical_analyzer.analyze_text(text)
        document.vocabulary.lexical_map = lexical_map

        # Optionally add pre-reading primer (uses shared lexical_map)
        if self.primer_generator:
            document = self.primer_generator.enhance_document(
                document, lexical_map=lexical_map
            )

        # Optionally enhance with interactive traps
        if self.trap_generator and self.level <= ScaffoldLevel.LOW:
            document = self.trap_generator.enhance_document(document)

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
        # Reset scaffolding context for new document
        if self.scaffold_context:
            self.scaffold_context.reset()

        if not self.chunker.needs_chunking(text):
            # Single chunk - simple case (no adaptive fading for single chunk)
            exclusion_prompt = ""
            if self.scaffold_context:
                # For single chunk, still track but no exclusions on first pass
                exclusion_prompt = self.scaffold_context.format_exclusion_prompt()
                self.scaffold_context.update_exposure(text)

            return self.llm_client.transform_with_validation(
                text,
                is_continuation=False,
                is_final=True,
                level=self.level,
                exclusion_prompt=exclusion_prompt,
            )

        # Multi-chunk processing with adaptive scaffolding
        transformed_parts: list[str] = []

        for chunk_text, is_first, is_last in self.chunker.chunk_text(text):
            # Get exclusion prompt based on words seen so far
            exclusion_prompt = ""
            if self.scaffold_context:
                exclusion_prompt = self.scaffold_context.format_exclusion_prompt()

            transformed = self.llm_client.transform_with_validation(
                chunk_text,
                is_continuation=not is_first,
                is_final=is_last,
                level=self.level,
                exclusion_prompt=exclusion_prompt,
            )
            transformed_parts.append(transformed)

            # Update exposure after processing this chunk
            if self.scaffold_context:
                self.scaffold_context.update_exposure(chunk_text)

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
        document = self.parser.parse(transformed, images=images)

        # Add vocabulary metadata with scaffold level
        document.vocabulary = VocabularyMetadata(scaffold_level=self.level)

        # Always run lexical analysis (decoupled from primer/traps)
        lexical_map = self.lexical_analyzer.analyze_text(text)
        document.vocabulary.lexical_map = lexical_map

        # Optionally add pre-reading primer (uses shared lexical_map)
        if self.primer_generator:
            document = self.primer_generator.enhance_document(
                document, lexical_map=lexical_map
            )

        # Optionally enhance with interactive traps
        if self.trap_generator and self.level <= ScaffoldLevel.LOW:
            document = self.trap_generator.enhance_document(document)

        return document
