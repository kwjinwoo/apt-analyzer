import urllib.error

import pytest

from apt_analyzer.acquisition import (
    AuthenticationError,
    AvailabilityError,
    DataGoKrClient,
    ParsingError,
    ProtocolError,
    SourceOutcome,
    load_service_key,
)


def test_encoded_service_key_is_not_double_encoded() -> None:
    client = DataGoKrClient(service_key="abc%2Fdef%2Bghi%3D")

    url = client.build_url("https://example.test/items", {"pageNo": "1"})

    assert "serviceKey=abc%2Fdef%2Bghi%3D" in url
    assert "%252F" not in url


def test_valid_empty_xml_is_distinct_from_failure() -> None:
    client = DataGoKrClient(service_key="encoded")

    result = client.parse_xml(
        b"<response><header><resultCode>000</resultCode><resultMsg>OK</resultMsg></header>"
        b"<body><items/><totalCount>0</totalCount></body></response>"
    )

    assert result.outcome is SourceOutcome.EMPTY
    assert result.records == ()


def test_source_failures_have_distinct_types() -> None:
    client = DataGoKrClient(service_key="encoded")
    with pytest.raises(AuthenticationError):
        client.parse_xml(
            b"<response><resultCode>30</resultCode><resultMsg>service key invalid</resultMsg></response>"
        )
    with pytest.raises(ProtocolError):
        client.parse_xml(
            b"<response><resultCode>99</resultCode><resultMsg>bad request</resultMsg></response>"
        )
    with pytest.raises(ParsingError):
        client.parse_xml(b"not xml")


def test_transport_retry_is_bounded_and_exhaustion_is_availability_failure() -> None:
    calls = 0

    def unavailable(_url: str, _timeout: float) -> bytes:
        nonlocal calls
        calls += 1
        raise urllib.error.URLError("offline")

    client = DataGoKrClient("encoded", transport=unavailable, retries=2)
    with pytest.raises(AvailabilityError):
        client.get_xml("https://example.test", {}, source="test")
    assert calls == 3


def test_load_service_key_prefers_process_environment_over_dotenv(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DATA_GO_KR_SERVICE_KEY", "process-sentinel")
    (tmp_path / ".env").write_text("DATA_GO_KR_SERVICE_KEY=dotenv-sentinel\n", encoding="utf-8")

    assert load_service_key(tmp_path) == "process-sentinel"


def test_load_service_key_falls_back_to_dotenv(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("DATA_GO_KR_SERVICE_KEY", raising=False)
    (tmp_path / ".env").write_text("DATA_GO_KR_SERVICE_KEY=dotenv-sentinel\n", encoding="utf-8")

    assert load_service_key(tmp_path) == "dotenv-sentinel"


def test_load_service_key_fails_when_sources_are_missing(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("DATA_GO_KR_SERVICE_KEY", raising=False)

    with pytest.raises(AuthenticationError, match="DATA_GO_KR_SERVICE_KEY"):
        load_service_key(tmp_path)
