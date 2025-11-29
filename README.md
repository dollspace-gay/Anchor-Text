# Anchor Text

**Rehabilitate readers betrayed by the education system.**

Anchor Text transforms documents using the **Literacy Bridge Protocol** to help "three-cueing" readers passively learn phonics. Instead of guessing words from context, readers are forced to decode each word through visual formatting cues.

## The Problem

Many readers learned to read using the "three-cueing" method, which encourages guessing words based on:
- Picture clues
- Context clues
- First letter only

This creates readers who *appear* fluent but struggle with unfamiliar words because they never learned to decode (sound out) words properly.

## The Solution

Anchor Text applies the **Literacy Bridge Protocol** - a set of formatting rules that force decoding:

1. **Root Anchoring** - Bold the root morpheme in multisyllabic words
   - `unpredictable` → `**un**predict**able**`

2. **Syllable Breaking** - Insert middle dots (·) for 3+ syllable words
   - `philosophy` → `phi·los·o·phy`

3. **Syntactic Spine** - Bold subjects, italicize verbs
   - `**The cat** *sat* on the mat.`

4. **Layout Engineering** - One clause per line, max 3 lines per paragraph

5. **Decoder's Trap** - Comprehension question after each paragraph requiring specific word decoding
   - `[Decoder Check: What four-syllable word means "basic"?]`

## Advanced Features

### Scaffolding Levels

Anchor Text supports 5 scaffolding levels that gradually reduce support as the reader improves:

| Level | Name | Description |
|-------|------|-------------|
| 1 (default) | MAX | Full formatting: bold roots, syllable breaks, syntactic spine, decoder checks |
| 2 | HIGH | Most formatting, slightly reduced decoder check frequency |
| 3 | MED | Balanced support: syllable breaks and occasional decoder checks |
| 4 | LOW | Minimal formatting: only difficult words get syllable breaks |
| 5 | MIN | Near-normal text: very rare formatting, subtle highlights only |

```bash
# Use scaffolding level 3 (medium support)
python anchor.py document.pdf --level 3

# Use minimal support (level 5)
python anchor.py document.pdf -l 5
```

### Enhanced Decoder Traps

Generate multiple-choice decoder traps with "lookalike" distractors that test true decoding ability:

```bash
python anchor.py document.pdf --enhanced-traps
```

This generates traps like:
> **Decoder Check:** Which word means "guess based on evidence"?
> - A) hypothesize ✓
> - B) hypnotize (looks similar but different meaning)
> - C) synthesize (similar ending)
> - D) hospitalize (similar beginning)

The lookalike words force readers to decode each option rather than guessing from context.

### Pre-Reading Primer

Add a warm-up section at the beginning of documents with the most challenging vocabulary:

```bash
python anchor.py document.pdf --primer
```

The primer includes:
- **Difficult word identification** - Automatically finds words with high syllable counts, irregular phonetics, and academic vocabulary
- **Pronunciation guides** - Syllable breakdowns with stress markers (hy-POTH-eh-sis)
- **Brief definitions** - Simple explanations for context
- **Practice exercises** - Syllable counting activities

### Vocabulary Guide

Generate a companion vocabulary guide PDF alongside the transformed document:

```bash
python anchor.py document.pdf --vocab-guide
```

The guide includes:
- **Word families** - Groups words by common roots (predict, dictate, contradict → all from Latin "dict")
- **Morpheme analysis** - Prefix, root, and suffix breakdowns
- **Difficulty tiers** - Words organized by complexity level
- **Practice exercises** - Fill-in-the-blank and word family matching

## Installation

```bash
# Clone the repository
git clone https://github.com/dollspace-gay/Anchor-Text.git
cd anchor-text

# Install dependencies
pip install -r requirements.txt

# Or install as a package
pip install -e .
```

## Quick Start

```bash
# Transform a single file
python anchor.py document.pdf

# Transform all files in a folder
python anchor.py /path/to/folder

# Use a specific AI model
python anchor.py document.docx --model openai/gpt-4o

# Use scaffolding level 3 with pre-reading primer
python anchor.py document.pdf --level 3 --primer

# Full features: enhanced traps + vocabulary guide
python anchor.py document.pdf --enhanced-traps --vocab-guide
```

## Configuration

1. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```

2. Add your API key:
   ```
   GEMINI_API_KEY=your-api-key-here
   ```

### Supported AI Providers

| Provider | Model Example | API Key Variable |
|----------|---------------|------------------|
| Google Gemini (default) | `gemini/gemini-3-pro-preview` | `GEMINI_API_KEY` |
| OpenAI | `openai/gpt-4o` | `OPENAI_API_KEY` |
| Anthropic | `anthropic/claude-sonnet-4-20250514` | `ANTHROPIC_API_KEY` |
| Ollama (local) | `ollama/llama3.1` | Set `OLLAMA_API_BASE` |

## Supported File Formats

| Format | Extension | Read | Write |
|--------|-----------|------|-------|
| Plain Text | `.txt` | Yes | Yes |
| PDF | `.pdf` | Yes | Yes |
| Word | `.docx` | Yes | Yes |
| OpenDocument | `.odt` | Yes | Yes |
| Rich Text | `.rtf` | Yes | Yes |
| E-book | `.epub` | Yes | Yes |

## Usage Examples

### Single File
```bash
# Input: report.pdf
# Output: report-anchor.pdf
python anchor.py report.pdf
```

### Batch Processing
```bash
# Process all supported files in a directory
python anchor.py ./documents/

# Files are saved alongside originals with -anchor suffix
# novel.epub → novel-anchor.epub
# chapter1.docx → chapter1-anchor.docx
```

### Custom Output Location
```bash
python anchor.py input.pdf -o /custom/path/output.pdf
```

### Verbose Mode
```bash
python anchor.py document.pdf -v
```

### Using Advanced Features

```bash
# Gradually reduce support as reader improves
python anchor.py chapter1.pdf --level 1   # Full support (default)
python anchor.py chapter2.pdf --level 2   # Slightly reduced
python anchor.py chapter3.pdf --level 3   # Medium support
python anchor.py chapter4.pdf --level 4   # Low support
python anchor.py chapter5.pdf --level 5   # Minimal support

# Add pre-reading warm-up with vocabulary primer
python anchor.py textbook.pdf --primer

# Generate enhanced multiple-choice decoder traps
python anchor.py novel.epub --enhanced-traps

# Create companion vocabulary guide
python anchor.py document.docx --vocab-guide
# Output: document-anchor.docx + document-vocab-guide.pdf

# Combine all features
python anchor.py textbook.pdf --level 2 --primer --enhanced-traps --vocab-guide
```

## Example Output

**Original text:**
> The scientists hypothesized about the results. The data showed unexpected patterns.

**Transformed text:**
> **The sci·en·tists** *hy·poth·e·sized* about the re·sults.
> **The data** *showed* un·ex·pect·ed patterns.
>
> [Decoder Check: What did the scientists do about the results?]

## How It Works

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Input File │────▶│  Extract    │────▶│   LLM       │
│  (PDF, DOCX)│     │  Text       │     │  Transform  │
└─────────────┘     └─────────────┘     └─────────────┘
                                               │
                                               ▼
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│ Output File │◀────│  Render     │◀────│   Parse     │
│ (Same fmt)  │     │  Format     │     │  Markdown   │
└─────────────┘     └─────────────┘     └─────────────┘
```

1. **Read** - Extract text (and images) from input document
2. **Chunk** - Split large documents to fit within token limits
3. **Transform** - AI applies Literacy Bridge Protocol formatting
4. **Parse** - Convert markdown output to intermediate representation
5. **Write** - Render to output format with proper styling

## Project Structure

```
anchor-text/
├── anchor.py              # CLI entry point
├── requirements.txt       # Dependencies
├── .env.example          # Configuration template
├── src/anchor_text/
│   ├── cli.py            # Command-line interface
│   ├── config.py         # Settings management
│   ├── core/
│   │   └── transformer.py    # Main orchestration
│   ├── llm/
│   │   ├── client.py     # LiteLLM wrapper
│   │   ├── prompts.py    # System prompts (all 5 levels)
│   │   ├── chunker.py    # Document splitting
│   │   └── traps.py      # Enhanced decoder trap generator
│   ├── lexical/
│   │   ├── analyzer.py   # Lexical Cartography analysis
│   │   ├── guide.py      # Vocabulary guide generator
│   │   └── primer.py     # Pre-reading primer generator
│   ├── formats/
│   │   ├── txt_handler.py
│   │   ├── pdf_handler.py
│   │   ├── docx_handler.py
│   │   ├── odt_handler.py
│   │   ├── rtf_handler.py
│   │   └── epub_handler.py
│   └── formatting/
│       ├── ir.py         # Intermediate representation
│       └── parser.py     # Markdown parser
└── tests/                # Test suite
```

## Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run tests with coverage
pytest --cov=anchor_text

# Format code
black src/ tests/

# Lint
ruff check src/ tests/
```

## CLI Options

| Option | Short | Description |
|--------|-------|-------------|
| `--output` | `-o` | Custom output path |
| `--model` | `-m` | LLM model to use (default: gemini/gemini-3-pro-preview) |
| `--level` | `-l` | Scaffolding level 1-5 (default: 1 = MAX support) |
| `--enhanced-traps` | `-e` | Generate multiple-choice traps with lookalike distractors |
| `--primer` | `-p` | Add pre-reading vocabulary warm-up section |
| `--vocab-guide` | `-g` | Generate companion vocabulary guide PDF |
| `--verbose` | `-v` | Show detailed processing information |

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ANCHOR_TEXT_MODEL` | `gemini/gemini-3-pro-preview` | Default AI model |
| `ANCHOR_TEXT_CHUNK_SIZE` | `3000` | Max tokens per chunk |
| `ANCHOR_TEXT_TEMPERATURE` | `0.3` | AI creativity (lower = more consistent) |
| `ANCHOR_TEXT_MAX_RETRIES` | `3` | Retry attempts on validation failure |

## Troubleshooting

### "Your default credentials were not found"
You're using the wrong API key variable. For Google AI Studio:
```
GEMINI_API_KEY=your-key-here
```
Not `GOOGLE_API_KEY` (that's for Google Cloud/Vertex AI).

### Rate Limiting
The tool includes automatic retry with exponential backoff. For heavy usage, consider:
- Using a paid API tier
- Reducing `ANCHOR_TEXT_CHUNK_SIZE`
- Processing files sequentially

### Missing Formatting
If output is missing bold/italic/syllable breaks:
- The tool auto-retries up to 3 times
- Try a different model (some are better at following instructions)
- Check if the source text is extractable

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests: `pytest`
5. Submit a pull request

## License

MIT License - see [LICENSE](LICENSE) for details.

## Acknowledgments

- Built with [LiteLLM](https://github.com/BerriAI/litellm) for universal LLM support
- PDF handling via [pdfplumber](https://github.com/jsvine/pdfplumber) and [ReportLab](https://www.reportlab.com/)
- Inspired by the science of reading and structured literacy approaches
