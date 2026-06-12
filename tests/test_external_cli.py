import json
from pathlib import Path

from click.testing import CliRunner
from PIL import Image
from pypdf import PdfReader
from reportlab.pdfgen import canvas

from autograph.cli import main


def _signature_png(path: Path) -> None:
    Image.new("RGBA", (240, 80), (0, 0, 0, 255)).save(path)


def _external_contract(path: Path) -> None:
    c = canvas.Canvas(str(path), pagesize=(612, 792))
    c.setFont("Helvetica", 10)
    c.drawString(72, 720, "External vendor contract")
    c.drawString(72, 150, "Signature: ______________________________")
    c.save()


def test_external_cli_plan_preview_and_approved_sign(tmp_path: Path):
    pdf = tmp_path / "external.pdf"
    plan_json = tmp_path / "plan.json"
    preview_pdf = tmp_path / "preview.pdf"
    signed_pdf = tmp_path / "signed.pdf"
    sig = tmp_path / "alice.png"
    _external_contract(pdf)
    _signature_png(sig)
    runner = CliRunner()

    plan_result = runner.invoke(
        main,
        ["plan-external", str(pdf), "--signer", "Alice Kim", "--output", str(plan_json)],
    )
    assert plan_result.exit_code == 0, plan_result.output
    payload = json.loads(plan_json.read_text())
    assert payload["requires_approval"] is True
    assert payload["placements"][0]["signer"] == "Alice Kim"

    preview_result = runner.invoke(
        main,
        ["preview-plan", str(pdf), "--plan", str(plan_json), "--output", str(preview_pdf)],
    )
    assert preview_result.exit_code == 0, preview_result.output
    assert preview_pdf.exists()

    blocked_result = runner.invoke(
        main,
        [
            "sign-plan",
            str(pdf),
            "--plan",
            str(plan_json),
            "--signature",
            f"Alice Kim={sig}",
            "--output",
            str(signed_pdf),
        ],
    )
    assert blocked_result.exit_code == 1, blocked_result.output
    assert json.loads(blocked_result.output)["signed"] is False

    signed_result = runner.invoke(
        main,
        [
            "sign-plan",
            str(pdf),
            "--plan",
            str(plan_json),
            "--signature",
            f"Alice Kim={sig}",
            "--approved",
            "--output",
            str(signed_pdf),
        ],
    )
    assert signed_result.exit_code == 0, signed_result.output
    assert json.loads(signed_result.output)["signed"] is True
    assert len(PdfReader(str(signed_pdf)).pages) == 1
