from __future__ import annotations

import json
from pathlib import Path

import click

from autograph.detectors import find_signature_requests
from autograph.models import SignResult
from autograph.parsers import extract_text, sniff_document_type
from autograph.signers.docx import sign_docx
from autograph.signers.pdf import sign_pdf


@click.group()
def main() -> None:
    """AUTOgraph document inspection and autograph stamping."""


@main.command()
@click.argument("document", type=click.Path(exists=True, dir_okay=False, path_type=Path))
def inspect(document: Path) -> None:
    """Inspect a document and print signer placeholders as JSON."""
    kind = sniff_document_type(document)
    text = extract_text(document)
    requests = find_signature_requests(text)
    payload = {
        "document": str(document),
        "format": kind,
        "signature_requests": [request.model_dump() for request in requests],
    }
    click.echo(json.dumps(payload, ensure_ascii=False, indent=2))


@main.command()
@click.argument("document", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--signer", required=True, help="Signer name to match in placeholders.")
@click.option(
    "--signature",
    "signature_path",
    required=True,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Autograph image path, preferably PNG with transparency.",
)
@click.option("--output", required=True, type=click.Path(dir_okay=False, path_type=Path))
def sign(document: Path, signer: str, signature_path: Path, output: Path) -> None:
    """Place a stored autograph image into a PDF or DOCX document."""
    kind = sniff_document_type(document)
    output.parent.mkdir(parents=True, exist_ok=True)
    if kind == "pdf":
        result = sign_pdf(document, output, signature_path, signer=signer)
    elif kind == "docx":
        result = sign_docx(document, output, signature_path, signer=signer)
    else:
        text = extract_text(document)
        requests = find_signature_requests(text)
        result = SignResult(
            input_path=document,
            output_path=output,
            signed=False,
            format=kind,
            warnings=[
                (
                    f"{kind.upper()} write support is not deterministic yet; "
                    "convert to PDF/DOCX first."
                ),
                f"Detected signers: {', '.join(r.signer for r in requests) or '(none)'}",
            ],
        )
    click.echo(result.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
