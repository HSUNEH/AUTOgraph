from __future__ import annotations

import json
from pathlib import Path

import click

from autograph.detectors import find_signature_requests
from autograph.external_pdf import (
    plan_external_pdf,
    preview_external_pdf_plan,
    sign_external_pdf_plan,
)
from autograph.models import SignaturePlan, SignResult
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


@main.command("plan-external")
@click.argument("document", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--signer", "signers", multiple=True, required=True, help="Signer name in order.")
@click.option("--output", required=True, type=click.Path(dir_okay=False, path_type=Path))
def plan_external(document: Path, signers: tuple[str, ...], output: Path) -> None:
    """Plan approval-required candidate placements for a third-party PDF."""
    output.parent.mkdir(parents=True, exist_ok=True)
    plan = plan_external_pdf(document, signers=list(signers))
    output.write_text(plan.model_dump_json(indent=2), encoding="utf-8")
    click.echo(plan.model_dump_json(indent=2))


@main.command("preview-plan")
@click.argument("document", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option(
    "--plan",
    "plan_path",
    required=True,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
)
@click.option("--output", required=True, type=click.Path(dir_okay=False, path_type=Path))
def preview_plan(document: Path, plan_path: Path, output: Path) -> None:
    """Draw visible candidate boxes from an external-document plan."""
    output.parent.mkdir(parents=True, exist_ok=True)
    plan = SignaturePlan.model_validate_json(plan_path.read_text(encoding="utf-8"))
    result = preview_external_pdf_plan(document, output, plan)
    click.echo(result.model_dump_json(indent=2))


def _parse_signature_options(items: tuple[str, ...]) -> dict[str, Path]:
    signatures: dict[str, Path] = {}
    for item in items:
        if "=" not in item:
            raise click.BadParameter("signature must be NAME=PATH")
        name, value = item.split("=", 1)
        path = Path(value).expanduser()
        if not path.exists():
            raise click.BadParameter(f"signature path does not exist: {path}")
        signatures[name] = path
    return signatures


@main.command("sign-plan")
@click.argument("document", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option(
    "--plan",
    "plan_path",
    required=True,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
)
@click.option("--signature", "signature_items", multiple=True, required=True, help="NAME=PATH")
@click.option("--approved", is_flag=True, help="Required to sign third-party document plans.")
@click.option("--output", required=True, type=click.Path(dir_okay=False, path_type=Path))
def sign_plan(
    document: Path,
    plan_path: Path,
    signature_items: tuple[str, ...],
    approved: bool,
    output: Path,
) -> None:
    """Sign an external-document plan only after explicit approval."""
    output.parent.mkdir(parents=True, exist_ok=True)
    plan = SignaturePlan.model_validate_json(plan_path.read_text(encoding="utf-8"))
    result = sign_external_pdf_plan(
        document,
        output,
        plan,
        signatures=_parse_signature_options(signature_items),
        approved=approved,
    )
    click.echo(result.model_dump_json(indent=2))
    if not result.signed:
        raise click.exceptions.Exit(1)


if __name__ == "__main__":
    main()
