from autograph.detectors import find_signature_requests


def test_finds_named_signature_placeholders_in_english_and_korean():
    text = "Vendor: Acme\n{{signature: Alice Kim}}\n담당자 서명: [SIGN: 홍길동]"

    requests = find_signature_requests(text)

    assert [request.signer for request in requests] == ["Alice Kim", "홍길동"]
    assert requests[0].placeholder == "{{signature: Alice Kim}}"
    assert requests[1].placeholder == "[SIGN: 홍길동]"


def test_deduplicates_same_signer_while_preserving_first_placeholder():
    text = "{{signature: ST}}\nSome terms\n[SIGN: ST]"

    requests = find_signature_requests(text)

    assert len(requests) == 1
    assert requests[0].signer == "ST"
    assert requests[0].placeholder == "{{signature: ST}}"
