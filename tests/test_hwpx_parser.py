import zipfile
from pathlib import Path

import pytest

from autograph.parsers import extract_text, sniff_document_type


def test_extracts_text_from_hwpx_zip_xml(tmp_path: Path):
    hwpx = tmp_path / "proposal.hwpx"
    with zipfile.ZipFile(hwpx, "w") as archive:
        archive.writestr("mimetype", "application/hwp+zip")
        archive.writestr(
            "Contents/section0.xml",
            """<?xml version='1.0' encoding='UTF-8'?>
            <hp:sec xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph">
              <hp:t>계약서</hp:t><hp:t>{{signature: 홍길동}}</hp:t>
            </hp:sec>
            """,
        )

    assert sniff_document_type(hwpx) == "hwpx"
    assert "{{signature: 홍길동}}" in extract_text(hwpx)


def test_hwpx_extraction_rejects_oversized_untrusted_archive_member(tmp_path: Path):
    hwpx = tmp_path / "bomb.hwpx"
    with zipfile.ZipFile(hwpx, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("Contents/section0.xml", "<root>" + ("x" * 2_100_000) + "</root>")

    with pytest.raises(ValueError, match="too large"):
        extract_text(hwpx)
