from pathlib import Path

from PIL import Image
from pypdf import PdfReader
from reportlab.pdfgen import canvas

from autograph.signers.pdf import sign_pdf, sign_pdf_batch


def _signature_png(path: Path, color: tuple[int, int, int, int]) -> None:
    Image.new("RGBA", (240, 80), color).save(path)


def _make_pdf(path: Path, pages: list[list[str]]) -> None:
    c = canvas.Canvas(str(path), pagesize=(420, 240))
    for page_number, lines in enumerate(pages, start=1):
        c.setFont("Helvetica-Bold", 14)
        c.drawString(40, 200, f"AUTOgraph scenario page {page_number}")
        c.setFont("Helvetica", 11)
        y = 155
        for line in lines:
            c.drawString(40, y, line)
            y -= 38
        c.showPage()
    c.save()


def _image_xobject_count(path: Path) -> int:
    count = 0
    reader = PdfReader(str(path))
    for page in reader.pages:
        resources = page.get("/Resources", {})
        xobjects = resources.get("/XObject", {})
        count += len(xobjects)
    return count


def test_sign_pdf_five_pages_signs_placeholder_on_last_page(tmp_path: Path):
    source = tmp_path / "five-pages-last-signature.pdf"
    output = tmp_path / "signed.pdf"
    alice = tmp_path / "alice.png"
    _signature_png(alice, (0, 0, 0, 255))
    _make_pdf(
        source,
        [
            ["Body page 1"],
            ["Body page 2"],
            ["Body page 3"],
            ["Body page 4"],
            ["Final approval", "Signer: {{signature: Alice Kim}}"],
        ],
    )

    result = sign_pdf(source, output, alice, signer="Alice Kim")

    assert result.signed is True
    assert [placement.page for placement in result.placements] == [4]
    assert _image_xobject_count(output) == 1


def test_sign_pdf_four_pages_signs_same_signer_on_pages_two_and_three(tmp_path: Path):
    source = tmp_path / "four-pages-two-signature-pages.pdf"
    output = tmp_path / "signed.pdf"
    alice = tmp_path / "alice.png"
    _signature_png(alice, (0, 0, 0, 255))
    _make_pdf(
        source,
        [
            ["Cover"],
            ["Clause A", "Signer: {{signature: Alice Kim}}"],
            ["Clause B", "Signer: {{signature: Alice Kim}}"],
            ["Appendix"],
        ],
    )

    result = sign_pdf(source, output, alice, signer="Alice Kim")

    assert result.signed is True
    assert [placement.page for placement in result.placements] == [1, 2]
    assert _image_xobject_count(output) == 2


def test_sign_pdf_batch_signs_registered_people_across_document(tmp_path: Path):
    source = tmp_path / "multi-signer.pdf"
    output = tmp_path / "signed.pdf"
    alice = tmp_path / "alice.png"
    bob = tmp_path / "bob.png"
    charlie = tmp_path / "charlie.png"
    _signature_png(alice, (0, 0, 0, 255))
    _signature_png(bob, (255, 0, 0, 255))
    _signature_png(charlie, (0, 0, 255, 255))
    _make_pdf(
        source,
        [
            ["Vendor", "Signer: {{signature: Alice Kim}}"],
            ["Reviewer", "Signer: {{signature: Bob Lee}}"],
            ["Approver", "[SIGN: Charlie Park]"],
        ],
    )

    result = sign_pdf_batch(
        source,
        output,
        signatures={
            "Alice Kim": alice,
            "Bob Lee": bob,
            "Charlie Park": charlie,
        },
    )

    assert result.signed is True
    assert [(p.signer, p.page) for p in result.placements] == [
        ("Alice Kim", 0),
        ("Bob Lee", 1),
        ("Charlie Park", 2),
    ]
    assert _image_xobject_count(output) == 3
