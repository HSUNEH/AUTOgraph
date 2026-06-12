# AUTOgraph

Agent-ready document autograph placement for proposals, contracts, and approval forms.

AUTOgraph scans incoming PDF, DOCX, HWP, and HWPX documents for signer cues, plans candidate signature locations, and places stored autograph images only through deterministic document tools. It does not ask an LLM to blindly draw on a document.

## MVP status

- PDF: text extraction, placeholder detection, visual autograph stamp overlay. Fails closed if a placeholder cannot be mapped to PDF coordinates.
- PDF multi-page: repeated placeholders for the same signer are stamped across all detected pages; batch API supports multiple registered signers in one pass.
- External PDFs: marker-free third-party PDFs can be planned from signature labels such as `Signature:` / `Sign:` / `서명`. This mode always requires preview + explicit approval before signing.
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

Third-party external PDF flow, where the sender did not include AUTOgraph markers:

```bash
autograph plan-external vendor-contract.pdf \
  --signer "Alice Kim" \
  --signer "Bob Lee" \
  --output plan.json

autograph preview-plan vendor-contract.pdf \
  --plan plan.json \
  --output preview.pdf

autograph sign-plan vendor-contract.pdf \
  --plan plan.json \
  --signature "Alice Kim=$HOME/.signatures/alice.png" \
  --signature "Bob Lee=$HOME/.signatures/bob.png" \
  --approved \
  --output signed.pdf
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

## External contract mode

External documents are treated differently from templates you control:

1. Detect candidate signature areas from PDF text positions around labels like `Signature:`, `Sign:`, `Seal/Sign:`, `서명`, and `날인`.
2. Produce a `SignaturePlan` JSON with page/x/y/width/height, confidence, reason, and a SHA-256 fingerprint of the planned document.
3. Generate a preview PDF with visible candidate boxes.
4. Refuse to sign unless `--approved` is explicitly passed.

This is the intended agent contract for Codex, Claude Code, or an MCP wrapper:

```text
agent receives external contract
→ run `autograph plan-external`
→ inspect plan JSON and warnings
→ run `autograph preview-plan`
→ ask the human to approve or adjust
→ run `autograph sign-plan --approved`
```

The agent may reason about warnings and ask for approval, but the deterministic AUTOgraph tool owns coordinate extraction and PDF mutation. `sign-plan` rejects mismatched document fingerprints and invalid/out-of-bounds placements.

## Security model

AUTOgraph creates visual autograph stamps. It does **not** create cryptographic digital signatures or legal identity proofs. Keep autograph images in a secure store and run automation only for trusted workflows.

External-contract mode is intentionally heuristic and approval-gated. Candidate detection is not a guarantee that the selected location is legally or visually correct.
