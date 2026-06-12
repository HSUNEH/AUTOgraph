from __future__ import annotations

import re

from autograph.models import SignatureRequest

_EXPLICIT_PATTERNS = [
    re.compile(r"\{\{\s*signature\s*:\s*(?P<signer>[^}]+?)\s*\}\}", re.IGNORECASE),
    re.compile(r"\[\s*SIGN\s*:\s*(?P<signer>[^\]]+?)\s*\]", re.IGNORECASE),
]

_KOREAN_LABEL_PATTERN = re.compile(
    r"(?P<label>서명|사인|날인)\s*[:：]?\s*(?P<signer>[가-힣A-Za-z][가-힣A-Za-z\s]{1,30})"
)


def _clean_signer(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip(" :：\t\n\r")


def find_signature_requests(text: str) -> list[SignatureRequest]:
    """Find explicit signer/autograph cues in extracted document text.

    AUTOgraph intentionally prefers explicit placeholders. Implicit legal wording such as
    "signature" can be ambiguous and should be reviewed before automation signs documents.
    """

    requests: list[SignatureRequest] = []
    seen: set[str] = set()

    for pattern in _EXPLICIT_PATTERNS:
        for match in pattern.finditer(text):
            signer = _clean_signer(match.group("signer"))
            key = signer.casefold()
            if signer and key not in seen:
                seen.add(key)
                requests.append(SignatureRequest(signer=signer, placeholder=match.group(0)))

    if requests:
        return requests

    for match in _KOREAN_LABEL_PATTERN.finditer(text):
        signer = _clean_signer(match.group("signer"))
        key = signer.casefold()
        if signer and key not in seen:
            seen.add(key)
            requests.append(SignatureRequest(signer=signer, placeholder=match.group(0)))

    return requests
