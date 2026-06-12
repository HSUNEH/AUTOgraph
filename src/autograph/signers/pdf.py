from __future__ import annotations

import io
import shutil
from collections.abc import Iterator
from pathlib import Path

from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas

from autograph.detectors import find_signature_requests
from autograph.models import SignaturePlacement, SignResult


def _iter_text_positions(path: Path) -> Iterator[tuple[int, str, float, float]]:
    reader = PdfReader(str(path))
    for page_index, page in enumerate(reader.pages):
        positions: list[tuple[int, str, float, float]] = []

        def visitor_text(
            text,  # noqa: ANN001
            cm,  # noqa: ANN001, ARG001
            tm,  # noqa: ANN001
            font_dict,  # noqa: ANN001, ARG001
            font_size,  # noqa: ANN001, ARG001
            *,
            current_page: int = page_index,
            current_positions: list[tuple[int, str, float, float]] = positions,
        ):
            if text.strip():
                current_positions.append((current_page, text, float(tm[4]), float(tm[5])))

        page.extract_text(visitor_text=visitor_text)
        yield from positions


def _find_placeholder_position(path: Path, placeholder: str) -> SignaturePlacement | None:
    positions = _find_placeholder_positions(path, placeholder)
    return positions[0] if positions else None


def _find_placeholder_positions(path: Path, placeholder: str) -> list[SignaturePlacement]:
    placements: list[SignaturePlacement] = []
    for page, text, x, y in _iter_text_positions(path):
        if placeholder in text:
            placements.append(
                SignaturePlacement(
                    signer="",
                    page=page,
                    x=x,
                    y=max(y - 18, 0),
                    width=120,
                    height=40,
                    placeholder=placeholder,
                )
            )
    return placements


def _write_pdf_with_placements(
    reader: PdfReader,
    output_path: Path,
    placements: list[tuple[SignaturePlacement, Path]],
) -> None:
    by_page: dict[int, list[tuple[SignaturePlacement, Path]]] = {}
    for placement, signature_path in placements:
        if placement.page is None:
            continue
        by_page.setdefault(placement.page, []).append((placement, signature_path))

    writer = PdfWriter()
    for index, page in enumerate(reader.pages):
        writer.add_page(page)
        page_placements = by_page.get(index, [])
        if not page_placements:
            continue
        page_size = page.mediabox
        packet = io.BytesIO()
        overlay_canvas = canvas.Canvas(
            packet,
            pagesize=(float(page_size.width), float(page_size.height)),
        )
        for placement, signature_path in page_placements:
            overlay_canvas.drawImage(
                str(signature_path),
                placement.x or 72,
                placement.y or 72,
                width=placement.width,
                height=placement.height,
                preserveAspectRatio=True,
                mask="auto",
            )
        overlay_canvas.save()
        packet.seek(0)
        overlay = PdfReader(packet)
        writer.pages[index].merge_page(overlay.pages[0])

    with output_path.open("wb") as handle:
        writer.write(handle)


def sign_pdf(
    input_path: str | Path,
    output_path: str | Path,
    signature_path: str | Path,
    *,
    signer: str,
    width: float = 120,
    height: float = 40,
) -> SignResult:
    input_path = Path(input_path)
    output_path = Path(output_path)
    signature_path = Path(signature_path)

    reader = PdfReader(str(input_path))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    requests = find_signature_requests(text)
    request = next((item for item in requests if item.signer.casefold() == signer.casefold()), None)
    if request is None:
        shutil.copyfile(input_path, output_path)
        return SignResult(
            input_path=input_path,
            output_path=output_path,
            signed=False,
            format="pdf",
            warnings=[f"No signature placeholder found for signer: {signer}"],
        )

    first_placement = _find_placeholder_position(input_path, request.placeholder)
    if first_placement is None:
        shutil.copyfile(input_path, output_path)
        return SignResult(
            input_path=input_path,
            output_path=output_path,
            signed=False,
            format="pdf",
            warnings=[
                f"Found placeholder for {signer}, but could not locate its PDF coordinates."
            ],
        )

    placements = _find_placeholder_positions(input_path, request.placeholder)
    for placement in placements:
        placement.signer = signer
        placement.width = width
        placement.height = height

    _write_pdf_with_placements(
        reader,
        output_path,
        [(placement, signature_path) for placement in placements],
    )

    return SignResult(
        input_path=input_path,
        output_path=output_path,
        signed=True,
        format="pdf",
        placements=placements,
    )


def sign_pdf_batch(
    input_path: str | Path,
    output_path: str | Path,
    *,
    signatures: dict[str, str | Path],
    width: float = 120,
    height: float = 40,
) -> SignResult:
    input_path = Path(input_path)
    output_path = Path(output_path)
    signature_paths = {signer.casefold(): Path(path) for signer, path in signatures.items()}

    reader = PdfReader(str(input_path))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    requests = find_signature_requests(text)

    placements: list[SignaturePlacement] = []
    overlay_jobs: list[tuple[SignaturePlacement, Path]] = []
    warnings: list[str] = []
    for request in requests:
        signature_path = signature_paths.get(request.signer.casefold())
        if signature_path is None:
            warnings.append(f"No registered signature image for signer: {request.signer}")
            continue
        request_positions = _find_placeholder_positions(input_path, request.placeholder)
        if not request_positions:
            warnings.append(
                f"Found placeholder for {request.signer}, but could not locate its PDF coordinates."
            )
            continue
        for placement in request_positions:
            placement.signer = request.signer
            placement.width = width
            placement.height = height
            placements.append(placement)
            overlay_jobs.append((placement, signature_path))

    if not placements:
        shutil.copyfile(input_path, output_path)
        return SignResult(
            input_path=input_path,
            output_path=output_path,
            signed=False,
            format="pdf",
            warnings=warnings or ["No signable PDF placeholders found."],
        )

    _write_pdf_with_placements(reader, output_path, overlay_jobs)
    return SignResult(
        input_path=input_path,
        output_path=output_path,
        signed=True,
        format="pdf",
        placements=placements,
        warnings=warnings,
    )
