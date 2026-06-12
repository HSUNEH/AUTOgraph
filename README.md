# AUTOgraph

Agent-ready document autograph placement for proposals, contracts, and approval forms.

AUTOgraph scans incoming PDF, DOCX, HWP, and HWPX documents for signer cues such as `{{signature: Alice Kim}}`, `[SIGN: Alice Kim]`, and Korean `서명` labels, then places a stored autograph image into the matching signature location when the format supports deterministic writing.

## MVP status

- PDF: text extraction, placeholder detection, visual autograph stamp overlay. Fails closed if a placeholder cannot be mapped to PDF coordinates.
- PDF multi-page: repeated placeholders for the same signer are stamped across all detected pages; batch API supports multiple registered signers in one pass.
- DOCX: placeholder detection and inline autograph image replacement, including placeholders split across Word runs.
- HWPX: bounded ZIP/XML text extraction and signer detection. Writing is routed through the conversion pipeline in the CLI roadmap.
- HWP: optional parser hook for text extraction when `hwp-hwpx-parser` is installed; write support is planned through HWPX/PDF conversion.

## Install

```bash
uv tool install .
# or
pipx install .
```

## Usage

```bash
autograph inspect contract.pdf
autograph sign contract.pdf --signer "Alice Kim" --signature ~/.signatures/alice.png --output signed.pdf
```

Python batch signing:

```python
from autograph.signers.pdf import sign_pdf_batch

sign_pdf_batch(
    "contract.pdf",
    "signed.pdf",
    signatures={
        "Alice Kim": "~/.signatures/alice.png",
        "Bob Lee": "~/.signatures/bob.png",
    },
)
```

## Placeholder conventions

Preferred explicit placeholders:

```text
{{signature: Alice Kim}}
[SIGN: Alice Kim]
서명: [SIGN: 홍길동]
```

The explicit marker keeps automation auditable: AUTOgraph only signs when it finds the requested signer.

## Security model

AUTOgraph creates visual autograph stamps. It does **not** create cryptographic digital signatures or legal identity proofs. Keep autograph images in a secure store and run automation only for trusted workflows.
