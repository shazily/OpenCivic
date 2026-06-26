"""Governance report export helpers (CSV and minimal PDF stub)."""

from __future__ import annotations

import base64


def build_governance_csv(totals: dict[str, int]) -> str:
    """Serialize governance metrics as CSV text."""
    lines = ["metric,value"]
    for key, value in totals.items():
        lines.append(f"{key},{value}")
    return "\n".join(lines) + "\n"


def _minimal_pdf_bytes(lines: list[str]) -> bytes:
    """Build a tiny valid PDF with one text block (no external dependencies)."""
    text = "\\n".join(line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)") for line in lines)
    stream = f"BT /F1 11 Tf 72 720 Td ({text}) Tj ET"
    stream_bytes = stream.encode("latin-1", errors="replace")
    objects: list[bytes] = []
    offsets: list[int] = []

    def add_object(content: bytes) -> None:
        offsets.append(sum(len(part) for part in objects))
        objects.append(content)

    add_object(b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n")
    add_object(b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n")
    add_object(b"3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R/Contents 4 0 R>>endobj\n")
    add_object(
        f"4 0 obj<</Length {len(stream_bytes)}>>stream\n".encode()
        + stream_bytes
        + b"\nendstream\nendobj\n"
    )

    header = b"%PDF-1.4\n"
    body = b"".join(objects)
    xref_start = len(header) + len(body)
    xref = b"xref\n0 5\n0000000000 65535 f \n"
    for offset in offsets:
        xref += f"{offset + len(header):010d} 00000 n \n".encode()
    trailer = b"trailer<</Size 5/Root 1 0 R>>\nstartxref\n" + str(xref_start).encode() + b"\n%%EOF\n"
    return header + body + xref + trailer


def build_governance_pdf_base64(totals: dict[str, int], *, days: int) -> str:
    """Return base64-encoded minimal PDF stub for steward governance reports."""
    lines = [f"OpenCivic governance summary ({days} days)"]
    for key, value in totals.items():
        lines.append(f"{key}: {value}")
    pdf_bytes = _minimal_pdf_bytes(lines)
    return base64.b64encode(pdf_bytes).decode("ascii")
