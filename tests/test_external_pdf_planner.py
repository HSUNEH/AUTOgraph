from pathlib import Path

from PIL import Image
from pypdf import PdfReader
from reportlab.pdfgen import canvas

from autograph.external_pdf import (
    plan_external_pdf,
    preview_external_pdf_plan,
    sign_external_pdf_plan,
)


def _signature_png(path: Path) -> None:
    Image.new("RGBA", (240, 80), (0, 0, 0, 255)).save(path)


def _external_contract(path: Path) -> None:
    c = canvas.Canvas(str(path), pagesize=(612, 792))
    c.setFont("Helvetica", 10)
    c.drawString(72, 730, "SERVICE AGREEMENT")
    for idx in range(18):
        c.drawString(
            72,
            700 - idx * 22,
            f"Clause {idx + 1}. The parties agree to commercially reasonable terms and review.",
        )
    c.drawString(72, 165, "Client Representative")
    c.drawString(72, 142, "Signature: ______________________________")
    c.drawString(330, 165, "Vendor Representative")
    c.drawString(330, 142, "Signature: ______________________________")
    c.save()


def _korean_external_contract(path: Path) -> None:
    c = canvas.Canvas(str(path), pagesize=(612, 792))
    c.setFont("Helvetica", 10)
    c.drawString(72, 730, "Korean-style approval sheet")
    c.drawString(72, 180, "Applicant")
    c.drawString(72, 150, "Sign: __________________")
    c.drawString(320, 180, "Approver")
    # Use ASCII fallback in fixture so reportlab Helvetica keeps extractable text.
    # Production detector includes Korean labels too.
    c.drawString(320, 150, "Seal/Sign: __________________")
    c.save()


def test_plans_external_pdf_signature_label_candidates_without_markers(tmp_path: Path):
    pdf = tmp_path / "external.pdf"
    _external_contract(pdf)

    plan = plan_external_pdf(pdf, signers=["Alice Kim", "Bob Lee"])

    assert plan.requires_approval is True
    assert plan.source == "external-label-heuristic"
    assert [placement.signer for placement in plan.placements] == ["Alice Kim", "Bob Lee"]
    assert [placement.page for placement in plan.placements] == [0, 0]
    assert all(placement.placeholder is None for placement in plan.placements)
    assert all(placement.confidence < 1 for placement in plan.placements)
    assert plan.placements[0].x < plan.placements[1].x


def test_previews_external_pdf_plan_with_visible_candidate_boxes(tmp_path: Path):
    pdf = tmp_path / "external.pdf"
    preview = tmp_path / "preview.pdf"
    _external_contract(pdf)
    plan = plan_external_pdf(pdf, signers=["Alice Kim", "Bob Lee"])

    result = preview_external_pdf_plan(pdf, preview, plan)

    assert result.output_path == preview
    reader = PdfReader(str(preview))
    assert len(reader.pages) == 1
    assert preview.stat().st_size > pdf.stat().st_size
    assert len(result.placements) == 2


def test_signs_external_pdf_plan_only_when_approved(tmp_path: Path):
    pdf = tmp_path / "external.pdf"
    out = tmp_path / "signed.pdf"
    sig = tmp_path / "alice.png"
    _external_contract(pdf)
    _signature_png(sig)
    plan = plan_external_pdf(pdf, signers=["Alice Kim"])

    unapproved = sign_external_pdf_plan(
        pdf, out, plan, signatures={"Alice Kim": sig}, approved=False
    )
    assert unapproved.signed is False
    assert "requires explicit approval" in unapproved.warnings[0]

    approved = sign_external_pdf_plan(pdf, out, plan, signatures={"Alice Kim": sig}, approved=True)
    assert approved.signed is True
    assert approved.placements[0].signer == "Alice Kim"
    assert PdfReader(str(out)).pages


def test_external_plan_can_use_registered_signer_count_for_dense_forms(tmp_path: Path):
    pdf = tmp_path / "external-korean-style.pdf"
    _korean_external_contract(pdf)

    plan = plan_external_pdf(pdf, signers=["Alice Kim", "Charlie Park"])

    assert len(plan.placements) == 2
    assert plan.placements[0].width <= 120
    assert plan.placements[0].height <= 40
