"""Opt-in deterministic browser acceptance for the local workspace."""

from __future__ import annotations

import socket
import threading
import time
from datetime import date
from decimal import Decimal

import pytest
from playwright.sync_api import Page, expect, sync_playwright
from uvicorn import Config, Server

from apt_analyzer.domain import Apartment, NormalizedTransaction, TransactionType
from apt_analyzer.m1 import ApartmentCandidate, IdentityResolution, ResolutionStatus
from apt_analyzer.persistence import SQLiteStore
from apt_analyzer.web import create_app


class BrowserFixtureService:
    def search(self, name: str) -> tuple[ApartmentCandidate, ...]:
        values = (("a", "Alpha"), ("b", "Beta"))
        return tuple(
            ApartmentCandidate(key, label, "1234567890", f"{label} lot", f"{label} road")
            for key, label in values
            if name.lower() in label.lower()
        )

    def resolve(
        self, selected: ApartmentCandidate
    ) -> tuple[ApartmentCandidate, IdentityResolution]:
        apartment = Apartment(selected.source_id, selected.name)
        return selected, IdentityResolution(ResolutionStatus.RESOLVED, (selected,), apartment)

    def retrieve(
        self, _candidate: ApartmentCandidate, apartment: Apartment, period: object
    ) -> tuple[NormalizedTransaction, ...]:
        assert hasattr(period, "start")
        start = period.start  # type: ignore[attr-defined]
        return (
            NormalizedTransaction(
                apartment.internal_id,
                date(start.year, start.month, 15),
                100_000_000 + start.month * 1_000_000,
                Decimal("84"),
                TransactionType.BROKERED,
                False,
                source_name="MOLIT apartment sale transactions",
                source_record_id=f"{apartment.internal_id}-{start:%Y%m}",
            ),
        )


@pytest.mark.e2e
def test_browser_workspace_full_deterministic_flow() -> None:
    port_socket = socket.socket()
    port_socket.bind(("127.0.0.1", 0))
    port = port_socket.getsockname()[1]
    port_socket.close()
    app = create_app(search_service=BrowserFixtureService(), store=SQLiteStore(":memory:"))
    server = Server(Config(app, host="127.0.0.1", port=port, log_level="error"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    try:
        deadline = time.time() + 10
        while not server.started and time.time() < deadline:
            time.sleep(0.05)
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page: Page = browser.new_page()
            page.goto(f"http://127.0.0.1:{port}/")
            expect(page.locator("h1")).to_contain_text("apt-analyzer")
            page.get_by_label("Apartment name").fill("Alpha")
            page.get_by_role("button", name="Search").click()
            page.get_by_role("button", name="Select").click()
            page.locator('input[name="start"]').first.fill("2024-01-01")
            page.locator('input[name="end"]').first.fill("2024-12-31")
            page.get_by_role("button", name="Update SQLite").click()
            page.wait_for_load_state("networkidle")
            page.locator('input[name="start"]').last.fill("2024-01-01")
            page.locator('input[name="end"]').last.fill("2024-12-31")
            page.get_by_role("button", name="Analyze").click()
            page.wait_for_timeout(1000)
            expect(page.locator("#price-chart")).to_have_count(1)
            expect(page.locator("#volume-chart")).to_have_count(1)
            expect(page.locator("#price-chart")).to_have_attribute("data-chart-ready", "true")
            expect(page.locator("#volume-chart")).to_have_attribute("data-chart-ready", "true")
            assert page.locator("#price-chart").evaluate("(canvas) => canvas.width") > 0
            assert page.locator("#volume-chart").evaluate("(canvas) => canvas.width") > 0
            expect(page.locator("table").nth(1)).to_contain_text("2024-01")
            page.get_by_label("Apartment name").fill("Beta")
            page.get_by_role("button", name="Search").click()
            page.get_by_role("button", name="Select").click()
            expect(page.locator('select[name="apartment_ids"] option')).to_have_count(2)
            page.locator('input[name="start"]').first.fill("2024-01-01")
            page.locator('input[name="end"]').first.fill("2024-12-31")
            page.get_by_role("button", name="Update SQLite").click()
            comparison = page.locator('form[action="/comparison"]')
            comparison.evaluate(
                """(form) => {
                    form.elements.namedItem('start').value = '2024-01-01';
                    form.elements.namedItem('end').value = '2024-12-31';
                    form.submit();
                }"""
            )
            page.wait_for_load_state("networkidle")
            expect(page.get_by_role("heading", name="Comparison subjects")).to_be_visible()
            expect(page.locator("#workspace")).to_contain_text("complete")
            expect(page.locator("#workspace")).to_contain_text("1")
            assert (
                page.locator('form[action="/comparison"] input[aria-label="Overall start"]').count()
                == 1
            )
            assert page.locator("#price-chart").count() == 0
            expect(page.locator("#workspace")).not_to_contain_text("Underlying volume")
            expect(
                page.get_by_role("link", name="Download equivalent JSON export")
            ).to_have_attribute("href", "/export?kind=comparison")
            export_response = page.request.get(f"http://127.0.0.1:{port}/export?kind=comparison")
            assert export_response.ok and len(export_response.json()["subjects"]) == 2
            assert "encoded-secret" not in page.content()
            browser.close()
    finally:
        server.should_exit = True
        thread.join(timeout=5)
