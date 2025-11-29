"""Command-line interface for Anchor Text."""

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from anchor_text import __version__
from anchor_text.config import get_settings
from anchor_text.formats import SUPPORTED_EXTENSIONS
from anchor_text.formatting.ir import ScaffoldLevel
from anchor_text.core.transformer import TextTransformer
from anchor_text.llm.prompts import get_level_description
from anchor_text.lexical.analyzer import LexicalAnalyzer
from anchor_text.lexical.guide import CompanionGuideGenerator

app = typer.Typer(
    name="anchor-text",
    help="Transform text using the Literacy Bridge Protocol for phonics education.",
    add_completion=False,
)
console = Console()


def version_callback(value: bool) -> None:
    """Print version and exit."""
    if value:
        console.print(f"Anchor Text v{__version__}")
        raise typer.Exit()


def generate_output_path(input_path: Path, output_dir: Optional[Path] = None) -> Path:
    """Generate output path with -anchor suffix."""
    stem = input_path.stem
    suffix = input_path.suffix
    output_name = f"{stem}-anchor{suffix}"

    if output_dir:
        return output_dir / output_name
    return input_path.parent / output_name


def process_file(
    input_path: Path,
    output_path: Optional[Path],
    model: str,
    verbose: bool,
    level: int = ScaffoldLevel.MAX,
    enhanced_traps: bool = False,
    vocab_guide: bool = False,
    primer: bool = False,
    adaptive: bool = False,
    fade_threshold: Optional[int] = None,
) -> bool:
    """Process a single file. Returns True on success."""
    if not input_path.exists():
        console.print(f"[red]Error:[/red] File not found: {input_path}")
        return False

    ext = input_path.suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        console.print(
            f"[yellow]Skipping:[/yellow] {input_path.name} "
            f"(unsupported format: {ext})"
        )
        return False

    if output_path is None:
        output_path = generate_output_path(input_path)

    if verbose:
        console.print(f"[blue]Processing:[/blue] {input_path}")
        console.print(f"[blue]Output:[/blue] {output_path}")
        console.print(f"[blue]Model:[/blue] {model}")
        console.print(f"[blue]Level:[/blue] {level} ({get_level_description(level)})")
        if enhanced_traps:
            console.print("[blue]Enhanced traps:[/blue] Enabled")
        if vocab_guide:
            console.print("[blue]Vocabulary guide:[/blue] Will be generated")
        if primer:
            console.print("[blue]Pre-reading primer:[/blue] Enabled")
        if adaptive:
            threshold_msg = f" (threshold: {fade_threshold})" if fade_threshold else ""
            console.print(f"[blue]Adaptive scaffolding:[/blue] Enabled{threshold_msg}")

    try:
        transformer = TextTransformer(
            model=model,
            level=level,
            enhanced_traps=enhanced_traps,
            pre_reading_primer=primer,
            adaptive=adaptive,
            fade_threshold=fade_threshold,
        )
        document = transformer.transform_file(input_path, output_path)
        console.print(f"[green]Success:[/green] {output_path}")

        # Generate vocabulary guide if requested
        if vocab_guide:
            guide_path = output_path.parent / f"{output_path.stem}-vocab-guide.txt"
            analyzer = LexicalAnalyzer(model=model, use_llm=False)
            document = analyzer.enhance_document(document)

            if document.vocabulary and document.vocabulary.lexical_map:
                generator = CompanionGuideGenerator()
                guide = generator.generate(
                    document.vocabulary.lexical_map,
                    source_title=input_path.stem,
                )
                generator.save_as_text(guide, guide_path)
                console.print(f"[green]Vocabulary guide:[/green] {guide_path}")

        return True
    except Exception as e:
        console.print(f"[red]Error processing {input_path.name}:[/red] {e}")
        if verbose:
            console.print_exception()
        return False


def process_folder(
    folder_path: Path,
    model: str,
    verbose: bool,
    level: int = ScaffoldLevel.MAX,
    enhanced_traps: bool = False,
    vocab_guide: bool = False,
    primer: bool = False,
    adaptive: bool = False,
    fade_threshold: Optional[int] = None,
    recursive: bool = True,
) -> tuple[int, int]:
    """Process all supported files in a folder. Returns (success_count, fail_count)."""
    if not folder_path.is_dir():
        console.print(f"[red]Error:[/red] Not a directory: {folder_path}")
        return 0, 0

    # Find all supported files
    files: list[Path] = []
    for ext in SUPPORTED_EXTENSIONS:
        if recursive:
            files.extend(folder_path.rglob(f"*{ext}"))
        else:
            files.extend(folder_path.glob(f"*{ext}"))

    # Skip already-processed files (those ending in -anchor or -vocab-guide)
    files = [
        f for f in files
        if not f.stem.endswith("-anchor") and not f.stem.endswith("-vocab-guide")
    ]

    if not files:
        console.print(
            f"[yellow]No supported files found in {folder_path}[/yellow]\n"
            f"Supported formats: {', '.join(SUPPORTED_EXTENSIONS)}"
        )
        return 0, 0

    console.print(f"[blue]Found {len(files)} file(s) to process[/blue]")
    console.print(f"[blue]Level:[/blue] {level} ({get_level_description(level)})")
    if adaptive:
        console.print("[blue]Adaptive scaffolding:[/blue] Enabled")

    success_count = 0
    fail_count = 0

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Processing files...", total=len(files))

        for file_path in files:
            progress.update(task, description=f"Processing {file_path.name}...")
            if process_file(
                file_path, None, model, verbose, level, enhanced_traps,
                vocab_guide, primer, adaptive, fade_threshold
            ):
                success_count += 1
            else:
                fail_count += 1
            progress.advance(task)

    return success_count, fail_count


@app.command()
def main(
    path: Path = typer.Argument(
        ...,
        help="File or folder to process",
        exists=True,
    ),
    output: Optional[Path] = typer.Option(
        None,
        "--output",
        "-o",
        help="Output path (for single file only)",
    ),
    model: Optional[str] = typer.Option(
        None,
        "--model",
        "-m",
        help="LLM model to use (default: gemini/gemini-3-pro-preview)",
    ),
    level: int = typer.Option(
        1,
        "--level",
        "-l",
        min=1,
        max=5,
        help="Scaffolding level 1-5 (1=max support, 5=minimal). "
        "Level 1: Full formatting. Level 2: No syllable dots. "
        "Level 3: No root anchoring. Level 4: Traps only. Level 5: Plain layout.",
    ),
    enhanced_traps: bool = typer.Option(
        False,
        "--enhanced-traps",
        "-e",
        help="Generate enhanced decoder traps with lookalike distractors",
    ),
    vocab_guide: bool = typer.Option(
        False,
        "--vocab-guide",
        "-g",
        help="Generate a companion vocabulary guide with word families and exercises",
    ),
    primer: bool = typer.Option(
        False,
        "--primer",
        "-p",
        help="Add pre-reading warm-up section with difficult words at document start",
    ),
    adaptive: bool = typer.Option(
        False,
        "--adaptive",
        "-a",
        help="Enable adaptive scaffolding - fade support for words seen multiple times",
    ),
    fade_threshold: Optional[int] = typer.Option(
        None,
        "--fade-threshold",
        "-t",
        min=1,
        max=10,
        help="Occurrences before fading support (default: 3). Requires --adaptive",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Enable verbose output",
    ),
    version: bool = typer.Option(
        False,
        "--version",
        "-V",
        callback=version_callback,
        is_eager=True,
        help="Show version and exit",
    ),
) -> None:
    """
    Transform documents using the Literacy Bridge Protocol.

    Examples:

        python anchor.py document.pdf

        python anchor.py /path/to/folder

        python anchor.py file.docx --model openai/gpt-4o

        python anchor.py file.pdf --level 2  # No syllable dots

        python anchor.py file.pdf --level 3 --enhanced-traps  # Interactive traps

        python anchor.py file.pdf --vocab-guide  # Generate vocabulary guide

        python anchor.py file.pdf --primer  # Add pre-reading warm-up section

        python anchor.py file.pdf --adaptive  # Fade support for repeated words

        python anchor.py file.pdf --adaptive --fade-threshold 5  # Custom threshold
    """
    settings = get_settings()
    use_model = model or settings.default_model

    # Warn if fade_threshold specified without adaptive
    if fade_threshold is not None and not adaptive:
        console.print(
            "[yellow]Warning:[/yellow] --fade-threshold requires --adaptive"
        )

    if path.is_file():
        # Single file mode
        success = process_file(
            path, output, use_model, verbose, level, enhanced_traps,
            vocab_guide, primer, adaptive, fade_threshold
        )
        raise typer.Exit(0 if success else 1)
    else:
        # Folder mode
        if output is not None:
            console.print(
                "[yellow]Warning:[/yellow] --output is ignored in folder mode. "
                "Files will be saved alongside originals with -anchor suffix."
            )

        success, fail = process_folder(
            path, use_model, verbose, level, enhanced_traps,
            vocab_guide, primer, adaptive, fade_threshold
        )
        console.print(
            f"\n[bold]Complete:[/bold] {success} succeeded, {fail} failed"
        )
        raise typer.Exit(0 if fail == 0 else 1)


if __name__ == "__main__":
    app()
