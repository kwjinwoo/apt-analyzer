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

from apt_analyzer.apartment_data import ApartmentCandidate, IdentityResolution, ResolutionStatus
from apt_analyzer.domain import Apartment, NormalizedTransaction, TransactionType
from apt_analyzer.persistence import SQLiteStore
from apt_analyzer.web import create_app


class BrowserFixtureService:
    def search(self, name: str, *, sido_code: str = "11") -> tuple[ApartmentCandidate, ...]:
        time.sleep(0.08)
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
        time.sleep(0.08)
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
            expect(page.locator("h1")).to_contain_text("아파트 거래")
            page.get_by_label("아파트 이름").fill("Alpha")
            search_form = page.locator('form[action="/search"]')
            search_form.get_by_role("button", name="검색하기").click()
            expect(search_form.locator("#search-progress")).to_be_visible()
            expect(search_form.get_by_role("button", name="검색하기")).to_be_disabled()
            expect(page.locator('form[action="/search"] #search-progress')).to_be_hidden()
            expect(page.locator('form[action="/search"] button[type="submit"]')).to_be_enabled()
            page.get_by_role("button", name="이 단지 선택").click()
            update_form = page.locator('form[action="/update"]')
            update_form.locator('input[name="start"]').fill("2024-01-01")
            update_form.locator('input[name="end"]').fill("2024-12-31")
            update_form.get_by_role("button", name="SQLite 근거 갱신").click()
            expect(update_form.locator("#update-progress")).to_be_visible()
            expect(update_form.get_by_role("button", name="SQLite 근거 갱신")).to_be_disabled()
            page.wait_for_load_state("networkidle")
            expect(page.locator('form[action="/update"] #update-progress')).to_be_hidden()
            expect(page.locator('form[action="/update"] button[type="submit"]')).to_be_enabled()
            analysis_form = page.locator("#analysis-form")
            analysis_form.locator('input[name="start"]').fill("2024-01-01")
            analysis_form.locator('input[name="end"]').fill("2024-12-31")
            analysis_form.get_by_text("고급 분석 설정").click()
            analysis_form.locator('input[name="transaction_types"][value="direct"]').uncheck()
            analysis_form.locator('input[name="transaction_types"][value="unknown"]').uncheck()
            analysis_form.locator('input[name="household_count"]').fill("100")
            analysis_form.locator('input[name="household_source"]').fill("fixture")
            analysis_form.get_by_role("button", name="분석 실행").click()
            page.wait_for_timeout(1000)
            expect(page.locator("#price-chart")).to_have_count(1)
            expect(page.locator("#volume-chart")).to_have_count(1)
            expect(page.locator("#price-chart")).to_have_attribute("data-chart-ready", "true")
            expect(page.locator("#volume-chart")).to_have_attribute("data-chart-ready", "true")
            expect(page.get_by_role("table", name="핵심 분석 지표")).to_be_visible()
            context_details = page.locator("details.context-details")
            expect(context_details).not_to_have_attribute("open", "")
            context_details.locator("summary").click()
            expect(context_details).to_contain_text("재현 가능한 분석 조건")
            context_details.locator("summary").click()
            page.set_viewport_size({"width": 390, "height": 844})
            metric_box = page.get_by_role("table", name="핵심 분석 지표").bounding_box()
            assert page.locator(".metric-summary").evaluate(
                "node => node.scrollWidth <= node.clientWidth"
            )
            assert metric_box is not None
            assert metric_box["x"] >= 0 and metric_box["x"] + metric_box["width"] <= 391
            page.set_viewport_size({"width": 1280, "height": 900})
            assert page.locator("#price-chart").evaluate("(canvas) => canvas.width") > 0
            assert page.locator("#volume-chart").evaluate("(canvas) => canvas.width") > 0
            expect(page.get_by_role("table", name="월별 거래량")).to_contain_text("2024-01")
            editor = page.locator("#analysis-result-editor")
            expect(editor).to_be_visible()
            expect(
                editor.locator('input[name="transaction_types"][value="brokered"]')
            ).to_be_checked()
            expect(
                editor.locator('input[name="transaction_types"][value="direct"]')
            ).not_to_be_checked()
            expect(editor.locator('input[name="household_count"]')).to_have_value("100")
            expect(page.locator("#workspace")).to_contain_text("3개월 이동 평균")
            trend_details = page.locator("details", has_text="3개월 이동 평균 (참고 추세)")
            expect(trend_details).not_to_have_attribute("open", "")
            expect(
                trend_details.get_by_role("table", name="월별 3개월 거래량 평균")
            ).not_to_be_visible()
            trend_details.locator("summary").click()
            expect(
                trend_details.get_by_role("table", name="월별 3개월 거래량 평균")
            ).to_be_visible()
            editor.locator('input[name="start"]').fill("2024-02-01")
            editor.locator('input[name="end"]').fill("2024-06-30")
            with page.expect_response(lambda item: item.url.endswith("/analysis")):
                editor.get_by_role("button", name="이 기간으로 다시 분석").click()
            expect(page.get_by_role("table", name="월별 거래량")).not_to_contain_text("2024-01")
            editor = page.locator("#analysis-result-editor")
            expect(editor.locator('input[name="start"]')).to_have_value("2024-02-01")
            export_analysis = page.request.get(f"http://127.0.0.1:{port}/export?kind=analysis")
            assert (
                export_analysis.ok
                and export_analysis.json()["ui_context"]["overall_period"]["start"] == "2024-02-01"
            )
            second_search_form = page.locator('form[action="/search"]')
            second_search_form.get_by_label("아파트 이름").fill("Beta")
            expect(second_search_form.get_by_label("아파트 이름")).to_have_value("Beta")
            second_search_form.get_by_role("button", name="검색하기").click()
            expect(page.locator('form[action="/select"]')).to_be_visible()
            page.get_by_role("button", name="이 단지 선택").click()
            expect(page.locator('select[name="apartment_ids"] option')).to_have_count(2)
            page.locator('input[name="start"]').first.fill("2024-01-01")
            page.locator('input[name="end"]').first.fill("2024-12-31")
            second_update_form = page.locator('form[action="/update"]')
            second_update_form.get_by_role("button", name="SQLite 근거 갱신").click()
            expect(second_update_form.locator("#update-progress")).to_be_visible()
            expect(
                second_update_form.get_by_role("button", name="SQLite 근거 갱신")
            ).to_be_disabled()
            expect(page.locator('form[action="/update"] #update-progress')).to_be_hidden()
            expect(page.locator('form[action="/update"] button[type="submit"]')).to_be_enabled()
            comparison = page.locator('form[action="/comparison"]')
            comparison.evaluate(
                """(form) => {
                    form.elements.namedItem('start').value = '2024-01-01';
                    form.elements.namedItem('end').value = '2024-12-31';
                    form.submit();
                }"""
            )
            page.wait_for_load_state("networkidle")
            expect(page.get_by_role("heading", name="아파트 비교 결과")).to_be_visible()
            expect(page.locator("#workspace")).to_contain_text("완료")
            expect(page.locator("#workspace")).to_contain_text("1")
            assert page.locator('form[action="/comparison"] input[name="start"]').count() == 1
            assert page.locator("#price-chart").count() == 0
            expect(page.locator("#workspace")).not_to_contain_text("Underlying volume")
            expect(page.get_by_role("link", name="비교 결과 JSON 내려받기")).to_have_attribute(
                "href", "/export?kind=comparison"
            )
            export_response = page.request.get(f"http://127.0.0.1:{port}/export?kind=comparison")
            assert export_response.ok and len(export_response.json()["subjects"]) == 2
            assert "encoded-secret" not in page.content()
            browser.close()
    finally:
        server.should_exit = True
        thread.join(timeout=5)
