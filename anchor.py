#!/usr/bin/env python3
"""
Anchor Text - Literacy Bridge Protocol Text Transformer

Simple usage:
    python anchor.py document.pdf           # Outputs document-anchor.pdf
    python anchor.py /folder/path           # Processes all files in folder
    python anchor.py file.docx --model openai/gpt-4o  # Use specific model
"""

import sys
from pathlib import Path

# Add src to path for development
src_path = Path(__file__).parent / "src"
if src_path.exists():
    sys.path.insert(0, str(src_path))

from anchor_text.cli import app

if __name__ == "__main__":
    app()
