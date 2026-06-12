from pathlib import Path

from PIL import Image
from pypdf import PdfReader
from reportlab.pdfgen import canvas

from autograph.signers import pdf as pdf_signer
from autograph.signers.pdf import sign_pdf


def _make_pdf(path: Path) -> None:
    c = canvas.Canvas(str(path), pagesize=(300, 160))
    c.drawString(40, 90, "Signer: {{signature: Alice Kim}}")
    c.save()


def test_sign_pdf_stamps_signature_near_detected_placeholder(tmp_path: Path):
    source = tmp_path / "contract.pdf"
    signature = tmp_path / "alice.png"
    output = tmp_path / "signed.pdf"
    _make_pdf(source)
    Image.new("RGBA", (240, 80), (0, 0, 0, 0)).save(signature)

    result = sign_pdf(source, output, signature, signer="Alice Kim")

    reader = PdfReader(str(output))
    page = reader.pages[0]
    assert result.signed is True
    assert result.placements[0].page == 0
    assert "/XObject" in page["/Resources"]


def test_sign_pdf_fails_closed_when_placeholder_position_is_unknown(
    tmp_path: Path, monkeypatch
):
    source = tmp_path / "contract.pdf"
    signature = tmp_path / "alice.png"
    output = tmp_path / "signed.pdf"
    _make_pdf(source)
    Image.new("RGBA", (240, 80), (0, 0, 0, 0)).save(signature)
    monkeypatch.setattr(pdf_signer, "_find_placeholder_position", lambda *_args: None)

    result = sign_pdf(source, output, signature, signer="Alice Kim")

    assert result.signed is False
    assert result.placements == []
    assert "could not locate" in result.warnings[0]
