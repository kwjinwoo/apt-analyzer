"""Opt-in deterministic browser acceptance for the local workspace."""

from __future__ import annotations

import json
import socket
import threading
import time
from datetime import date
from decimal import Decimal

import pytest
from playwright.sync_api import Page, expect, sync_playwright
from uvicorn import Config, Server

from apt_analyzer.apartment_data import (
    ApartmentCandidate,
    ApartmentProfile,
    AreaHouseholdBand,
    IdentityResolution,
    ResolutionStatus,
)
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
        enriched = ApartmentCandidate(
            selected.source_id,
            selected.name,
            selected.legal_dong_code,
            selected.lot_address,
            selected.road_address,
            100,
            "K-APT apartment basic information",
            ApartmentProfile(
                buildings=3,
                approval_date=date(1999, 5, 3),
                highest_floor=20,
                heating="지역난방",
                hall_type="혼합식",
                builder="한신공영",
                developer="한국토지주택공사 LH",
                management="위탁관리",
                sale_type="분양",
                area_bands=(AreaHouseholdBand("≤60㎡", 100),),
            ),
        )
        return enriched, IdentityResolution(ResolutionStatus.RESOLVED, (enriched,), apartment)

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
            expect(page.get_by_role("button", name="기간 선택 시작")).to_have_count(0)
            expect(page.get_by_role("button", name="적용")).to_have_count(0)
            expect(page.get_by_role("table", name="핵심 분석 지표")).to_be_visible()
            profile = page.locator(".complex-profile")
            expect(profile).to_be_visible()
            expect(profile).to_contain_text("단지 기본 정보")
            expect(profile).to_contain_text("K-APT 면적 구간별 참고 근거")
            expect(profile).to_contain_text("검증된 전용면적별 세대수는 아직 확인되지 않았습니다")
            expect(profile.locator("details.complex-profile-bands-reference")).to_have_count(1)
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
            profile_box = profile.bounding_box()
            assert profile_box is not None
            assert profile.evaluate("node => node.scrollWidth <= node.clientWidth")
            assert profile_box["x"] >= 0 and profile_box["x"] + profile_box["width"] <= 391
            page.set_viewport_size({"width": 1280, "height": 900})
            assert page.locator("#price-chart").evaluate("(canvas) => canvas.width") > 0
            assert page.locator("#volume-chart").evaluate("(canvas) => canvas.width") > 0
            evidence_details = page.locator("details.monthly-evidence-details")
            expect(evidence_details).not_to_have_attribute("open", "")
            expect(evidence_details.get_by_role("table", name="월별 거래량")).not_to_be_visible()
            expect(
                evidence_details.get_by_role("table", name="월별 가격 중간값")
            ).not_to_be_visible()
            evidence_details.locator("summary").click()
            expect(evidence_details.get_by_role("table", name="월별 거래량")).to_contain_text(
                "2024-01"
            )
            expect(evidence_details.get_by_role("table", name="월별 가격 중간값")).to_be_visible()
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
            expect(page.locator("details.monthly-evidence-details")).not_to_contain_text("2024-01")
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


@pytest.mark.e2e
def test_chart_drag_previews_metrics_without_mutating_official_analysis() -> None:
    port_socket = socket.socket()
    port_socket.bind(("127.0.0.1", 0))
    port = port_socket.getsockname()[1]
    port_socket.close()
    app = create_app(
        search_service=BrowserFixtureService(),
        store=SQLiteStore(":memory:"),
        analysis_today=lambda: date(2026, 8, 30),
    )
    server = Server(Config(app, host="127.0.0.1", port=port, log_level="error"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    try:
        while not server.started:
            time.sleep(0.05)
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page()
            page.goto(f"http://127.0.0.1:{port}/")
            page.get_by_label("아파트 이름").fill("Alpha")
            page.locator('form[action="/search"]').get_by_role("button", name="검색하기").click()
            page.get_by_role("button", name="이 단지 선택").click()
            update = page.locator('form[action="/update"]')
            update.locator('input[name="start"]').fill("2020-09-01")
            update.locator('input[name="end"]').fill("2023-08-31")
            update.get_by_role("button", name="SQLite 근거 갱신").click()
            page.wait_for_load_state("networkidle")
            analysis = page.locator("#analysis-form")
            analysis.locator('input[name="start"]').fill("2020-09-01")
            analysis.locator('input[name="end"]').fill("2023-08-31")
            analysis.get_by_text("고급 분석 설정").click()
            analysis.locator('input[name="household_count"]').fill("100")
            analysis.locator('input[name="household_source"]').fill("fixture")
            analysis.get_by_role("button", name="분석 실행").click()
            page.wait_for_timeout(500)
            canvas = page.locator("#volume-chart")
            canvas.scroll_into_view_if_needed()
            expect(canvas).to_be_in_viewport()
            expect(page.get_by_role("button", name="기간 선택 시작")).to_have_count(0)
            expect(page.get_by_role("button", name="적용")).to_have_count(0)
            expect(page.get_by_role("button", name="취소")).to_have_count(0)
            expect(page.get_by_role("button", name="자동 기간으로 복원")).to_have_count(0)
            box = canvas.bounding_box()
            assert box is not None
            centers = canvas.get_attribute("data-period-centers")
            assert centers is not None
            values = json.loads(centers)
            labels = json.loads(canvas.get_attribute("data-period-labels") or "[]")
            start_index = labels.index("2021-09")
            end_index = start_index + 11
            summary_before = page.get_by_role("table", name="핵심 분석 지표").inner_text()
            editor = page.locator("#analysis-result-editor")
            editor_before = editor.locator("input").evaluate_all(
                "nodes => nodes.map(node => [node.name, node.value, node.checked])"
            )
            export_before = page.request.get(f"http://127.0.0.1:{port}/export?kind=analysis").json()
            preview_requests = 0

            def count_preview(request) -> None:
                nonlocal preview_requests
                if request.url.endswith("/analysis/preview"):
                    preview_requests += 1

            page.on("request", count_preview)
            page.mouse.move(box["x"] + values[start_index], box["y"] + box["height"] / 2)
            page.mouse.down()
            page.mouse.move(box["x"] + values[end_index], box["y"] + box["height"] / 2)
            assert preview_requests == 0
            with page.expect_response(
                lambda response: (
                    response.url.endswith("/analysis/preview") and response.request.method == "POST"
                )
            ):
                page.mouse.up()
            expect(page.locator("#brush-status")).to_contain_text("2021.09 ~ 2022.08")
            expect(canvas).to_have_attribute("data-selected-range", f"{start_index}:{end_index}")
            preview = page.locator("#analysis-preview")
            expect(preview).to_be_visible()
            expect(preview).to_contain_text("선택 기간 참고 미리보기")
            expect(preview).to_contain_text("유효 거래량12건")
            expect(preview).to_contain_text("거래회전율12.00%")
            expect(preview).to_contain_text("12건 / 100세대")
            expect(preview).to_contain_text("거래유지율100.00%")
            expect(preview).to_contain_text("2021.09~2022.08 12건 / 2020.09~2021.08 12건")
            expect(preview).to_contain_text("최대 낙폭(MDD)-9.82%")
            assert preview_requests == 1
            assert page.get_by_role("table", name="핵심 분석 지표").inner_text() == summary_before
            assert (
                editor.locator("input").evaluate_all(
                    "nodes => nodes.map(node => [node.name, node.value, node.checked])"
                )
                == editor_before
            )
            assert (
                page.request.get(f"http://127.0.0.1:{port}/export?kind=analysis").json()
                == export_before
            )

            page.set_viewport_size({"width": 390, "height": 844})
            expect(preview).to_be_visible()
            preview_box = preview.bounding_box()
            assert preview_box is not None
            assert preview.evaluate("node => node.scrollWidth <= node.clientWidth")
            assert preview_box["x"] >= 0 and preview_box["x"] + preview_box["width"] <= 391
            page.keyboard.press("Escape")
            expect(preview).to_be_hidden()
            expect(canvas).not_to_have_attribute(
                "data-selected-range", f"{start_index}:{end_index}"
            )

            page.set_viewport_size({"width": 1280, "height": 900})
            canvas.scroll_into_view_if_needed()
            box = canvas.bounding_box()
            assert box is not None
            values = json.loads(canvas.get_attribute("data-period-centers") or "[]")
            with page.expect_response(lambda response: response.url.endswith("/analysis/preview")):
                page.mouse.move(box["x"] + values[start_index], box["y"] + box["height"] / 2)
                page.mouse.down()
                page.mouse.move(box["x"] + values[end_index], box["y"] + box["height"] / 2)
                page.mouse.up()
            expect(preview).to_be_visible()
            page.locator("h1").click()
            expect(preview).to_be_hidden()

            evidence = page.locator("details.monthly-evidence-details")
            expect(evidence).not_to_have_attribute("open", "")
            expect(evidence.get_by_role("table", name="월별 거래량")).not_to_be_visible()
            expect(evidence.get_by_role("table", name="월별 가격 중간값")).not_to_be_visible()
            evidence.locator("summary").click()
            expect(evidence.get_by_role("table", name="월별 거래량")).to_be_visible()
            expect(evidence.get_by_role("table", name="월별 가격 중간값")).to_be_visible()
            browser.close()
    finally:
        server.should_exit = True
        thread.join(timeout=5)
