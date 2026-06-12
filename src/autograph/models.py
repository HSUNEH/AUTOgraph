from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field


class SignatureRequest(BaseModel):
    signer: str
    placeholder: str


class SignaturePlacement(BaseModel):
    signer: str
    page: int | None = None
    x: float | None = None
    y: float | None = None
    width: float = 120
    height: float = 40
    placeholder: str | None = None
    confidence: float = 1.0
    reason: str | None = None


class SignaturePlan(BaseModel):
    input_path: Path
    placements: list[SignaturePlacement] = Field(default_factory=list)
    source: str
    requires_approval: bool = True
    document_sha256: str | None = None
    warnings: list[str] = Field(default_factory=list)


class SignResult(BaseModel):
    input_path: Path
    output_path: Path
    signed: bool
    format: str
    placements: list[SignaturePlacement] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
