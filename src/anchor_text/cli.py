"""Command-line interface for Anchor Text."""

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from anchor_text import __version__
from anchor_text.config import get_settings
from anchor_text.formats import SUPPORTED_EXTENSIONS, get_handler
from anchor_text.core.transformer import TextTransformer

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

    try:
        transformer = TextTransformer(model=model)
        transformer.transform_file(input_path, output_path)
        console.print(f"[green]Success:[/green] {output_path}")
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

    # Skip already-processed files (those ending in -anchor)
    files = [f for f in files if not f.stem.endswith("-anchor")]

    if not files:
        console.print(
            f"[yellow]No supported files found in {folder_path}[/yellow]\n"
            f"Supported formats: {', '.join(SUPPORTED_EXTENSIONS)}"
        )
        return 0, 0

    console.print(f"[blue]Found {len(files)} file(s) to process[/blue]")

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
            if process_file(file_path, None, model, verbose):
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
    """
    settings = get_settings()
    use_model = model or settings.default_model

    if path.is_file():
        # Single file mode
        success = process_file(path, output, use_model, verbose)
        raise typer.Exit(0 if success else 1)
    else:
        # Folder mode
        if output is not None:
            console.print(
                "[yellow]Warning:[/yellow] --output is ignored in folder mode. "
                "Files will be saved alongside originals with -anchor suffix."
            )

        success, fail = process_folder(path, use_model, verbose)
        console.print(
            f"\n[bold]Complete:[/bold] {success} succeeded, {fail} failed"
        )
        raise typer.Exit(0 if fail == 0 else 1)


if __name__ == "__main__":
    app()
