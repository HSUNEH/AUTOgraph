# AUTOgraph external-document agent contract

AUTOgraph is not a vision-first signing bot. For third-party contracts, Codex, Claude Code, Hermes, or an MCP wrapper should act as an **orchestrator** around deterministic PDF tools.

## Goal

Handle PDFs from external parties that do not contain AUTOgraph placeholders.

The agent's job:

1. Run candidate planning.
2. Read warnings and confidence.
3. Produce a preview artifact for the human.
4. Ask for explicit approval or correction.
5. Only then call the signing command with `--approved`.

The agent must not invent coordinates or sign without approval.

## CLI contract

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

## Plan JSON shape

`plan-external` writes a `SignaturePlan`:

```json
{
  "input_path": "vendor-contract.pdf",
  "source": "external-label-heuristic",
  "requires_approval": true,
  "document_sha256": "...",
  "placements": [
    {
      "signer": "Alice Kim",
      "page": 0,
      "x": 158.6,
      "y": 131.0,
      "width": 120,
      "height": 36,
      "placeholder": null,
      "confidence": 0.62,
      "reason": "signature label near text: Signature: __________________"
    }
  ],
  "warnings": []
}
```

## Suggested Codex / Claude prompt

```text
You are operating AUTOgraph on an external PDF. Do not sign directly.

1. Run `autograph plan-external <pdf> --signer ... --output plan.json`.
2. Inspect plan.json. If warnings exist, summarize them.
3. Run `autograph preview-plan <pdf> --plan plan.json --output preview.pdf`.
4. Show the preview to the human and ask for approval or coordinate corrections.
5. Only after explicit approval, run `autograph sign-plan <pdf> --plan plan.json --signature "Name=/path/to/signature.png" --approved --output signed.pdf`.
6. Report the final path and the placement list.

Never fabricate coordinates. Never add `--approved` unless the human approved the preview.
If `sign-plan` is run without approval or with an invalid/mismatched plan, it emits JSON and exits non-zero.
```

## Future visual-agent extension

A visual model can be added as a candidate generator, not as the final signing authority:

```text
PDF render → visual candidate boxes → merge with text-label candidates → preview → human approval → deterministic sign
```

The output still must be a `SignaturePlan` with explicit coordinates, confidence, and reason.
Plans are bound to the source PDF by SHA-256 fingerprint and placements are validated against page bounds before preview/sign.
