"""Official public-data acquisition with explicit source outcomes and provenance."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, cast
from urllib.parse import quote, urlencode


class SourceOutcome(StrEnum):
    """Classify source responses without conflating empty data and failures."""

    RECORDS = "records"
    EMPTY = "empty"


class SourceError(RuntimeError):
    """Base error raised for an unsuccessful official-source operation."""


class AuthenticationError(SourceError):
    """Indicate that the source rejected the service key."""


class AvailabilityError(SourceError):
    """Indicate that bounded transport retries were exhausted."""


class ProtocolError(SourceError):
    """Indicate an unexpected HTTP or source result code."""


class ParsingError(SourceError):
    """Indicate malformed or structurally invalid source data."""


@dataclass(frozen=True, slots=True)
class SourceResult:
    """Carry parsed records and visible acquisition provenance."""

    outcome: SourceOutcome
    records: tuple[Mapping[str, str], ...]
    source: str
    fetched_at: datetime
    query: tuple[tuple[str, str], ...]
    from_cache: bool = False


Transport = Callable[[str, float], bytes]
RequestObserver = Callable[[str], None]


class DataGoKrClient:
    """Fetch XML from data.go.kr while preserving an already encoded key."""

    def __init__(
        self,
        service_key: str,
        *,
        transport: Transport | None = None,
        retries: int = 2,
        timeout: float = 10.0,
        request_observer: RequestObserver | None = None,
    ) -> None:
        """Configure credentials, transport limits, and an in-memory cache."""
        if not service_key.strip():
            raise ValueError("service key must not be empty")
        self._key = service_key.strip()
        self._transport = transport or self._urlopen
        self._retries = retries
        self._timeout = timeout
        self._request_observer = request_observer
        self._cache: dict[str, SourceResult] = {}

    def build_url(self, endpoint: str, params: Mapping[str, str]) -> str:
        """Build a query without encoding the already percent-encoded key again."""
        query = urlencode(params, quote_via=quote)
        separator = "&" if "?" in endpoint else "?"
        return f"{endpoint}{separator}serviceKey={self._key}&{query}"

    def get_xml(
        self,
        endpoint: str,
        params: Mapping[str, str],
        *,
        source: str,
        use_cache: bool = True,
    ) -> SourceResult:
        """Fetch and parse XML using bounded retries for transient failures."""
        url = self.build_url(endpoint, params)
        if use_cache and url in self._cache:
            cached = self._cache[url]
            return SourceResult(
                cached.outcome,
                cached.records,
                cached.source,
                cached.fetched_at,
                cached.query,
                from_cache=True,
            )
        for attempt in range(self._retries + 1):
            try:
                if self._request_observer is not None:
                    self._request_observer(endpoint)
                payload = self._transport(url, self._timeout)
                result = self.parse_xml(payload, source=source, query=params)
                self._cache[url] = result
                return result
            except AuthenticationError:
                raise
            except (urllib.error.URLError, TimeoutError, AvailabilityError) as error:
                if attempt == self._retries:
                    raise AvailabilityError("official source unavailable after retries") from error
                time.sleep(0.05 * (attempt + 1))
        raise AssertionError("unreachable")

    def parse_xml(
        self,
        payload: bytes,
        *,
        source: str = "data.go.kr",
        query: Mapping[str, str] | None = None,
    ) -> SourceResult:
        """Parse the common data.go.kr response envelope."""
        if payload.lstrip().startswith(b"{"):
            return self._parse_json(payload, source, query or {})
        try:
            root = ET.fromstring(payload)
        except ET.ParseError as error:
            raise ParsingError("source returned malformed XML") from error
        code = (root.findtext(".//resultCode") or "").strip()
        message = (root.findtext(".//resultMsg") or "").strip()
        if code not in {"000", "00"}:
            lowered = message.lower()
            if "service" in lowered and "key" in lowered or "인증" in message:
                raise AuthenticationError(f"source authentication failed ({code})")
            raise ProtocolError(f"source rejected request ({code or 'missing code'})")
        items = root.findall(".//items/item") or root.findall("./body/item")
        records = tuple({child.tag: (child.text or "").strip() for child in item} for item in items)
        return SourceResult(
            SourceOutcome.RECORDS if records else SourceOutcome.EMPTY,
            records,
            source,
            datetime.now(UTC),
            tuple(sorted((query or {}).items())),
        )

    def _parse_json(self, payload: bytes, source: str, query: Mapping[str, str]) -> SourceResult:
        """Parse the JSON form used by K-APT operations."""
        try:
            # JSON is an untyped external boundary; values are converted below.
            document: dict[str, Any] = json.loads(payload)
            envelope = cast(dict[str, object], document["response"])
            header = cast(dict[str, object], envelope["header"])
            body = cast(dict[str, object], envelope["body"])
            code = str(header["resultCode"])
            if code not in {"000", "00"}:
                raise ProtocolError(f"source rejected request ({code})")
            raw_values: object = body.get("items", body.get("item", []))
            if isinstance(raw_values, dict):
                value_dict = cast(dict[str, object], raw_values)
                raw_values = value_dict.get("item", [value_dict])
            if not isinstance(raw_values, list):
                raise TypeError("items must be a list")
            values = cast(list[dict[str, object]], raw_values)
            records_list: list[Mapping[str, str]] = []
            for row in values:
                records_list.append({str(k): str(v) for k, v in row.items()})
            records = tuple(records_list)
        except (KeyError, TypeError, ValueError) as error:
            raise ParsingError("source returned malformed JSON") from error
        return SourceResult(
            SourceOutcome.RECORDS if records else SourceOutcome.EMPTY,
            records,
            source,
            datetime.now(UTC),
            tuple(sorted(query.items())),
        )

    @staticmethod
    def _urlopen(url: str, timeout: float) -> bytes:
        request = urllib.request.Request(url, headers={"User-Agent": "apt-analyzer/0.1"})
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                if response.status != 200:
                    raise ProtocolError(f"unexpected HTTP status {response.status}")
                return response.read()
        except urllib.error.HTTPError as error:
            if error.code in {401, 403}:
                raise AuthenticationError("source authentication failed") from error
            if 500 <= error.code < 600:
                raise AvailabilityError("official source unavailable") from error
            raise ProtocolError(f"unexpected HTTP status {error.code}") from error


def load_service_key(root: Path | None = None) -> str:
    """Load the key from the environment, then a root .env without mutating it."""
    import os

    if value := os.environ.get("DATA_GO_KR_SERVICE_KEY"):
        return value
    env_path = (root or Path.cwd()) / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            key, separator, value = line.partition("=")
            if separator and key.strip() == "DATA_GO_KR_SERVICE_KEY":
                return value.strip().strip("'\"")
    raise AuthenticationError("DATA_GO_KR_SERVICE_KEY is not configured")
