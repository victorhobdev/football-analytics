from __future__ import annotations

import argparse
import textwrap
from pathlib import Path


def _escape_pdf_text(value: str) -> str:
    return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _build_pdf(pages_lines: list[list[str]], *, page_width: int = 595, page_height: int = 842) -> bytes:
    objects: list[bytes] = []

    # 1: Catalog
    # 2: Pages root
    # 3: Font
    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")

    kids_refs = []
    next_obj = 4
    for _ in pages_lines:
        kids_refs.append(f"{next_obj} 0 R")
        next_obj += 2
    objects.append(f"<< /Type /Pages /Count {len(pages_lines)} /Kids [{' '.join(kids_refs)}] >>".encode("latin-1"))
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier >>")

    page_obj = 4
    content_obj = 5
    for lines in pages_lines:
        page_dict = (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {page_width} {page_height}] "
            f"/Resources << /Font << /F1 3 0 R >> >> /Contents {content_obj} 0 R >>"
        )
        objects.append(page_dict.encode("latin-1"))

        text_commands = ["BT", "/F1 10 Tf", "12 TL", f"40 {page_height - 48} Td"]
        first = True
        for line in lines:
            escaped = _escape_pdf_text(line)
            if first:
                text_commands.append(f"({escaped}) Tj")
                first = False
            else:
                text_commands.append("T*")
                text_commands.append(f"({escaped}) Tj")
        text_commands.append("ET")
        stream = "\n".join(text_commands).encode("latin-1", errors="replace")
        content_stream = f"<< /Length {len(stream)} >>\nstream\n".encode("latin-1") + stream + b"\nendstream"
        objects.append(content_stream)

        page_obj += 2
        content_obj += 2

    buffer = bytearray()
    buffer.extend(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")

    offsets = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(buffer))
        buffer.extend(f"{index} 0 obj\n".encode("latin-1"))
        buffer.extend(obj)
        buffer.extend(b"\nendobj\n")

    xref_offset = len(buffer)
    total_objects = len(objects) + 1
    buffer.extend(f"xref\n0 {total_objects}\n".encode("latin-1"))
    buffer.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        buffer.extend(f"{offset:010d} 00000 n \n".encode("latin-1"))

    trailer = (
        f"trailer\n<< /Size {total_objects} /Root 1 0 R >>\n"
        f"startxref\n{xref_offset}\n%%EOF\n"
    )
    buffer.extend(trailer.encode("latin-1"))
    return bytes(buffer)


def render_markdown_to_pdf(input_path: Path, output_path: Path) -> None:
    text = input_path.read_text(encoding="utf-8")
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")

    wrapped_lines: list[str] = []
    for raw_line in normalized.split("\n"):
        if not raw_line:
            wrapped_lines.append("")
            continue
        chunks = textwrap.wrap(raw_line, width=95, break_long_words=False, break_on_hyphens=False)
        if not chunks:
            wrapped_lines.append("")
        else:
            wrapped_lines.extend(chunks)

    lines_per_page = 62
    pages_lines = [wrapped_lines[i : i + lines_per_page] for i in range(0, len(wrapped_lines), lines_per_page)]
    if not pages_lines:
        pages_lines = [[""]]

    pdf_bytes = _build_pdf(pages_lines)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(pdf_bytes)


def main() -> None:
    parser = argparse.ArgumentParser(description="Render markdown/plain text to a simple PDF.")
    parser.add_argument("--input", required=True, help="Input markdown path.")
    parser.add_argument("--output", required=True, help="Output PDF path.")
    args = parser.parse_args()

    render_markdown_to_pdf(Path(args.input), Path(args.output))


if __name__ == "__main__":
    main()
