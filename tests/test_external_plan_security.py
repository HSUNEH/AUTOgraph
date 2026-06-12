from pathlib import Path

from PIL import Image
from reportlab.pdfgen import canvas

from autograph.external_pdf import (
    plan_external_pdf,
    preview_external_pdf_plan,
    sign_external_pdf_plan,
)
from autograph.models import SignaturePlacement, SignaturePlan


def _signature_png(path: Path) -> None:
    Image.new("RGBA", (240, 80), (0, 0, 0, 255)).save(path)


def _pdf(path: Path, label_y: int = 100) -> None:
    c = canvas.Canvas(str(path), pagesize=(612, 792))
    c.setFont("Helvetica", 10)
    c.drawString(72, 720, f"External contract {label_y}")
    c.drawString(72, label_y, "Signature: ______________________________")
    c.save()


def test_external_plan_is_bound_to_document_fingerprint(tmp_path: Path):
    pdf = tmp_path / "external.pdf"
    _pdf(pdf)

    plan = plan_external_pdf(pdf, signers=["Alice Kim"])

    assert plan.document_sha256
    assert len(plan.document_sha256) == 64


def test_rejects_plan_for_different_document_even_when_approved(tmp_path: Path):
    original = tmp_path / "original.pdf"
    other = tmp_path / "other.pdf"
    out = tmp_path / "signed.pdf"
    sig = tmp_path / "alice.png"
    _pdf(original, label_y=100)
    _pdf(other, label_y=180)
    _signature_png(sig)
    plan = plan_external_pdf(original, signers=["Alice Kim"])

    result = sign_external_pdf_plan(other, out, plan, signatures={"Alice Kim": sig}, approved=True)

    assert result.signed is False
    assert "does not match plan fingerprint" in result.warnings[0]


def test_rejects_plan_without_document_fingerprint(tmp_path: Path):
    pdf = tmp_path / "external.pdf"
    out = tmp_path / "signed.pdf"
    sig = tmp_path / "alice.png"
    _pdf(pdf)
    _signature_png(sig)
    plan = plan_external_pdf(pdf, signers=["Alice Kim"])
    plan.document_sha256 = None

    result = sign_external_pdf_plan(pdf, out, plan, signatures={"Alice Kim": sig}, approved=True)

    assert result.signed is False
    assert "missing document fingerprint" in result.warnings[0]


def test_preview_rejects_plan_for_different_document(tmp_path: Path):
    original = tmp_path / "original.pdf"
    other = tmp_path / "other.pdf"
    preview = tmp_path / "preview.pdf"
    _pdf(original, label_y=100)
    _pdf(other, label_y=180)
    plan = plan_external_pdf(original, signers=["Alice Kim"])

    result = preview_external_pdf_plan(other, preview, plan)

    assert result.placements == []
    assert "does not match plan fingerprint" in result.warnings[0]


def test_rejects_fabricated_or_out_of_bounds_plan_coordinates(tmp_path: Path):
    pdf = tmp_path / "external.pdf"
    out = tmp_path / "signed.pdf"
    sig = tmp_path / "alice.png"
    _pdf(pdf)
    _signature_png(sig)
    real_plan = plan_external_pdf(pdf, signers=["Alice Kim"])
    bad_plan = SignaturePlan(
        input_path=pdf,
        source="external-label-heuristic",
        requires_approval=True,
        document_sha256=real_plan.document_sha256,
        placements=[
            SignaturePlacement(
                signer="Alice Kim",
                page=99,
                x=-100,
                y=float("nan"),
                width=5000,
                height=0,
                confidence=0.2,
                reason="fabricated",
            )
        ],
    )

    result = sign_external_pdf_plan(
        pdf, out, bad_plan, signatures={"Alice Kim": sig}, approved=True
    )

    assert result.signed is False
    assert any("Rejected invalid placement" in warning for warning in result.warnings)


def test_rejects_fractional_placement_extending_past_page_edge(tmp_path: Path):
    pdf = tmp_path / "external.pdf"
    out = tmp_path / "signed.pdf"
    sig = tmp_path / "alice.png"
    _pdf(pdf)
    _signature_png(sig)
    real_plan = plan_external_pdf(pdf, signers=["Alice Kim"])
    bad_plan = SignaturePlan(
        input_path=pdf,
        source="external-label-heuristic",
        requires_approval=True,
        document_sha256=real_plan.document_sha256,
        placements=[
            SignaturePlacement(
                signer="Alice Kim",
                page=0,
                x=600,
                y=100,
                width=12.5,
                height=20,
                confidence=0.2,
                reason="fractional out of bounds",
            )
        ],
    )

    result = sign_external_pdf_plan(
        pdf, out, bad_plan, signatures={"Alice Kim": sig}, approved=True
    )

    assert result.signed is False
    assert any("Rejected invalid placement" in warning for warning in result.warnings)
