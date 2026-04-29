from __future__ import annotations

import argparse
import sys
from pathlib import Path

from pypdf import PdfReader


def build_output_path(input_pdf: Path, output_arg: str | None) -> Path:
    """Return output .txt path from CLI args."""
    if output_arg:
        output_path = Path(output_arg)
        if output_path.suffix.lower() != ".txt":
            output_path = output_path.with_suffix(".txt")
        return output_path
    return input_pdf.with_suffix(".txt")


def extract_text_from_pdf(input_pdf: Path) -> str:
    """Extract text from all pages of a text-based PDF."""
    reader = PdfReader(str(input_pdf))
    page_texts: list[str] = []

    for page in reader.pages:
        text = page.extract_text() or ""
        page_texts.append(text.strip("\n"))

    # Keep page boundaries while avoiding excessive blank lines.
    non_empty_pages = [page for page in page_texts if page.strip()]
    return "\n\n".join(non_empty_pages).strip() + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract text from a text-based PDF into a .txt file."
    )
    parser.add_argument("input_pdf", help="Path to input PDF file")
    parser.add_argument(
        "-o",
        "--output",
        default=None,
        help="Path to output TXT file (default: same name as PDF)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    input_pdf = Path(args.input_pdf)
    if not input_pdf.exists():
        print(f"Error: file not found: {input_pdf}", file=sys.stderr)
        return 1
    if not input_pdf.is_file():
        print(f"Error: not a file: {input_pdf}", file=sys.stderr)
        return 1
    if input_pdf.suffix.lower() != ".pdf":
        print("Error: input file must have .pdf extension", file=sys.stderr)
        return 1

    output_txt = build_output_path(input_pdf, args.output)
    output_txt.parent.mkdir(parents=True, exist_ok=True)

    try:
        text = extract_text_from_pdf(input_pdf)
    except Exception as exc:  # noqa: BLE001
        print(f"Error while reading PDF: {exc}", file=sys.stderr)
        return 1

    output_txt.write_text(text, encoding="utf-8")
    print(f"Done. Text saved to: {output_txt}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
