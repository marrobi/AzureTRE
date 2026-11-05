"""Classifies result files for in-browser preview."""

import csv
import io
from pathlib import PurePosixPath

IMAGE = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"}
HTML = {".html", ".htm"}
TABLE = {".csv": ",", ".tsv": "\t"}
MARKDOWN = {".md", ".markdown"}
TEXT = {
    ".txt",
    ".log",
    ".json",
    ".yaml",
    ".yml",
    ".nf",
    ".config",
    ".mmd",
    ".fasta",
    ".fa",
    ".vcf",
    ".bed",
    ".gff",
    ".gtf",
    ".sam",
    ".out",
    ".err",
    ".sh",
    ".py",
    ".r",
    ".tab",
}
PDF = {".pdf"}
PREVIEW_LIMIT = 2 * 1024 * 1024
TABLE_ROWS = 500


def kind_for(name: str) -> str:
    suffix = PurePosixPath(name).suffix.lower()
    if suffix in IMAGE:
        return "image"
    if suffix in HTML:
        return "html"
    if suffix in TABLE:
        return "table"
    if suffix in MARKDOWN:
        return "markdown"
    if suffix in PDF:
        return "pdf"
    if suffix in TEXT or PurePosixPath(name).name in ("exit_code", "trace.txt"):
        return "text"
    return "binary"


def parse_table(name: str, data: bytes) -> tuple[list[str], list[dict], bool]:
    """Parse the start of a CSV/TSV file. Returns (columns, rows, truncated)."""
    delimiter = TABLE.get(PurePosixPath(name).suffix.lower(), ",")
    reader = csv.reader(io.StringIO(data.decode("utf-8", "replace")), delimiter=delimiter)
    header = next(reader, [])
    columns = [h or f"column_{i + 1}" for i, h in enumerate(header)]
    rows, truncated = [], False
    for i, record in enumerate(reader):
        if i >= TABLE_ROWS:
            truncated = True
            break
        rows.append({"_row": i, **{c: (record[j] if j < len(record) else "") for j, c in enumerate(columns)}})
    return columns, rows, truncated


def human_size(size: int | None) -> str:
    if size is None:
        return ""
    value = float(size)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    return f"{size} B"
