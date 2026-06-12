from __future__ import annotations

import hashlib
import io
import math
import shutil
from collections.abc import Mapping
from pathlib import Path

from pypdf import PdfReader, PdfWriter
from reportlab.lib.colors import Color, red
from reportlab.pdfgen import canvas

from autograph.models import SignaturePlacement, SignaturePlan, SignResult
from autograph.signers.pdf import _iter_text_positions, _write_pdf_with_placements

SIGNATURE_LABELS = (
    "signature",
    "sign:",
    "signed by",
    "applicant signature",
    "representative signature",
    "seal/sign",
    "서명",
    "날인",
    "서명란",
)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _looks_like_signature_label(text: str) -> bool:
    normalized = " ".join(text.casefold().split())
    return any(label in normalized for label in SIGNATURE_LABELS)


def _size_from_label_text(text: str) -> tuple[float, float]:
    # A rough deterministic fit for common external-contract labels. Dense table rows
    # often expose shorter label strings; long underline labels can take a standard stamp.
    underscore_count = text.count("_")
    if underscore_count >= 20:
        return 120, 36
    if underscore_count >= 8:
        return 96, 30
    return 88, 28


def _candidate_from_label(
    *,
    signer: str,
    page: int,
    text: str,
    x: float,
    y: float,
) -> SignaturePlacement:
    width, height = _size_from_label_text(text)
    # Put the autograph on the blank area right after the label when possible.
    # If the PDF text run contains a long label+underline, this still lands inside the
    # signature line instead of the left margin.
    label_offset = min(max(len(text.split("_")[0]) * 3.8, 34), 86)
    return SignaturePlacement(
        signer=signer,
        page=page,
        x=x + label_offset,
        y=max(y - 11, 0),
        width=width,
        height=height,
        placeholder=None,
        confidence=0.62,
        reason=f"signature label near text: {text.strip()[:80]}",
    )


def plan_external_pdf(
    input_path: str | Path,
    *,
    signers: list[str],
    max_candidates: int | None = None,
) -> SignaturePlan:
    """Plan candidate autograph placements for third-party PDFs without anchors.

    This mode intentionally returns approval-required candidates. It does not sign
    automatically because external contracts can be ambiguous.
    """

    input_path = Path(input_path)
    labels = [
        (page, text, x, y)
        for page, text, x, y in _iter_text_positions(input_path)
        if _looks_like_signature_label(text)
    ]
    if max_candidates is not None:
        labels = labels[:max_candidates]

    placements: list[SignaturePlacement] = []
    for signer, label in zip(signers, labels, strict=False):
        page, text, x, y = label
        placements.append(_candidate_from_label(signer=signer, page=page, text=text, x=x, y=y))

    warnings: list[str] = []
    if not labels:
        warnings.append("No external signature labels found.")
    if len(labels) < len(signers):
        warnings.append(
            f"Only found {len(labels)} signature label candidates "
            f"for {len(signers)} requested signers."
        )
    if len(labels) > len(signers):
        warnings.append(
            f"Found {len(labels)} signature label candidates "
            f"but only {len(signers)} signers were provided."
        )

    return SignaturePlan(
        input_path=input_path,
        placements=placements,
        source="external-label-heuristic",
        requires_approval=True,
        document_sha256=_sha256_file(input_path),
        warnings=warnings,
    )


def _document_matches_plan(input_path: Path, plan: SignaturePlan) -> tuple[bool, str | None]:
    if not plan.document_sha256:
        return False, "External document plan is missing document fingerprint."
    if _sha256_file(input_path) != plan.document_sha256:
        return False, "Input document does not match plan fingerprint."
    return True, None


def _valid_placements(
    reader: PdfReader,
    placements: list[SignaturePlacement],
) -> tuple[list[SignaturePlacement], list[str]]:
    valid: list[SignaturePlacement] = []
    warnings: list[str] = []
    for placement in placements:
        page_index = placement.page
        values = [placement.x, placement.y, placement.width, placement.height]
        finite = all(value is not None and math.isfinite(value) for value in values)
        if page_index is None or page_index < 0 or page_index >= len(reader.pages) or not finite:
            warnings.append(f"Rejected invalid placement for signer: {placement.signer}")
            continue
        page = reader.pages[page_index]
        page_width = float(page.mediabox.width)
        page_height = float(page.mediabox.height)
        x = placement.x or 0
        y = placement.y or 0
        if (
            placement.width <= 0
            or placement.height <= 0
            or x < 0
            or y < 0
            or x >= page_width
            or y >= page_height
            or x + placement.width > page_width
            or y + placement.height > page_height
        ):
            warnings.append(f"Rejected invalid placement for signer: {placement.signer}")
            continue
        valid.append(placement)
    return valid, warnings


def preview_external_pdf_plan(
    input_path: str | Path,
    output_path: str | Path,
    plan: SignaturePlan,
) -> SignResult:
    input_path = Path(input_path)
    output_path = Path(output_path)
    reader = PdfReader(str(input_path))
    writer = PdfWriter()
    matches_plan, fingerprint_warning = _document_matches_plan(input_path, plan)
    if not matches_plan:
        shutil.copyfile(input_path, output_path)
        return SignResult(
            input_path=input_path,
            output_path=output_path,
            signed=False,
            format="pdf-preview",
            placements=[],
            warnings=[fingerprint_warning or "Input document does not match plan."],
        )
    valid_placements, validation_warnings = _valid_placements(reader, plan.placements)

    by_page: dict[int, list[SignaturePlacement]] = {}
    for placement in valid_placements:
        if placement.page is not None:
            by_page.setdefault(placement.page, []).append(placement)

    for index, page in enumerate(reader.pages):
        writer.add_page(page)
        page_placements = by_page.get(index, [])
        if not page_placements:
            continue
        page_size = page.mediabox
        packet = io.BytesIO()
        c = canvas.Canvas(packet, pagesize=(float(page_size.width), float(page_size.height)))
        c.setStrokeColor(red)
        c.setFillColor(Color(1, 0, 0, alpha=0.08))
        for placement in page_placements:
            x = placement.x or 72
            y = placement.y or 72
            c.rect(x, y, placement.width, placement.height, stroke=1, fill=1)
            c.setFillColor(red)
            c.setFont("Helvetica", 7)
            c.drawString(x, y + placement.height + 3, f"candidate: {placement.signer}")
            c.setFillColor(Color(1, 0, 0, alpha=0.08))
        c.save()
        packet.seek(0)
        overlay = PdfReader(packet)
        writer.pages[index].merge_page(overlay.pages[0])

    with output_path.open("wb") as handle:
        writer.write(handle)

    return SignResult(
        input_path=input_path,
        output_path=output_path,
        signed=False,
        format="pdf-preview",
        placements=valid_placements,
        warnings=[*plan.warnings, *validation_warnings],
    )


def sign_external_pdf_plan(
    input_path: str | Path,
    output_path: str | Path,
    plan: SignaturePlan,
    *,
    signatures: Mapping[str, str | Path],
    approved: bool,
) -> SignResult:
    input_path = Path(input_path)
    output_path = Path(output_path)
    matches_plan, fingerprint_warning = _document_matches_plan(input_path, plan)
    if not matches_plan:
        shutil.copyfile(input_path, output_path)
        return SignResult(
            input_path=input_path,
            output_path=output_path,
            signed=False,
            format="pdf",
            placements=plan.placements,
            warnings=[fingerprint_warning or "Input document does not match plan."],
        )
    if not approved:
        shutil.copyfile(input_path, output_path)
        return SignResult(
            input_path=input_path,
            output_path=output_path,
            signed=False,
            format="pdf",
            placements=plan.placements,
            warnings=["External document plan requires explicit approval before signing."],
        )

    signature_paths = {signer.casefold(): Path(path) for signer, path in signatures.items()}
    overlay_jobs: list[tuple[SignaturePlacement, Path]] = []
    reader = PdfReader(str(input_path))
    valid_placements, validation_warnings = _valid_placements(reader, plan.placements)
    warnings = [*plan.warnings, *validation_warnings]
    for placement in valid_placements:
        signature_path = signature_paths.get(placement.signer.casefold())
        if signature_path is None:
            warnings.append(f"No registered signature image for signer: {placement.signer}")
            continue
        overlay_jobs.append((placement, signature_path))

    if not overlay_jobs:
        shutil.copyfile(input_path, output_path)
        return SignResult(
            input_path=input_path,
            output_path=output_path,
            signed=False,
            format="pdf",
            placements=plan.placements,
            warnings=warnings or ["No approved external placements could be signed."],
        )

    _write_pdf_with_placements(reader, output_path, overlay_jobs)
    return SignResult(
        input_path=input_path,
        output_path=output_path,
        signed=True,
        format="pdf",
        placements=[placement for placement, _ in overlay_jobs],
        warnings=warnings,
    )
