import json
from types import SimpleNamespace
import anthropic
import httpx2
import pytest
from app.pipeline import stages
from app.reports.generator import ReportService
from app.reports.slices import SECTION_IDS, build_slices
from app.reports.verification import verify_numbers
from app.tests.test_pipeline import WAIT_SECONDS, FakeSandbox, bundled_fetch, submit

DATA_MARKER = "Data for this section (JSON):\n"


@pytest.fixture(autouse=True)
def offline_market_data(monkeypatch):
    monkeypatch.setattr(stages, "fetch_ohlcv", bundled_fetch)


def tool_response(section_id: str, text: str, stop_reason: str = "tool_use", payload: dict | None = None):
    block = SimpleNamespace(
        type="tool_use",
        name="write_section",
        input=payload if payload is not None else {"id": section_id, "title": section_id.title(), "text": text},
    )
    return SimpleNamespace(stop_reason=stop_reason, content=[block])


class FakeClient:
    def __init__(self, responder=None):
        self.calls = []
        self.responder = responder or (lambda section_id, kwargs: tool_response(section_id, "The section reads clearly without figures."))
        self.messages = self

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self.responder(kwargs["tools"][0]["input_schema"]["properties"]["id"]["enum"][0], kwargs)


def service_with(client: FakeClient) -> ReportService:
    return ReportService(client_factory=lambda api_key, timeout: client)


def sent_slice(call: dict) -> dict:
    return json.loads(call["messages"][0]["content"].split(DATA_MARKER, 1)[1])


def test_verification_accepts_percent_forms_and_ignores_dates_identifiers_and_ordinals():
    text = (
        "The strategy returned 64.2% and the drawdown was 7.1%. "
        "On 2024-12-31 the rsi_14 and vol_20d features led, as section 3 explains. "
        "It made 12 trades."
    )
    result = verify_numbers({"summary": text}, {"summary": {"total_return": 0.642, "max_drawdown": -0.071, "n_trades": 12}})
    assert result["numbers_total"] == 3
    assert result["numbers_verified"] == 3
    assert result["flagged"] is False


def test_verification_rejects_a_number_absent_from_the_source():
    text = "Return was 64.2%. Sharpe was 1.37. There were 12 trades."
    result = verify_numbers({"summary": text}, {"summary": {"total_return": 0.642, "n_trades": 12}})
    assert result["numbers_verified"] == result["numbers_total"] - 1
    assert result["sections"]["summary"]["unverified"] == [{"number": "1.37", "sentence": "Sharpe was 1.37."}]
    assert result["flagged"] is True


def test_verification_handles_signs_thousands_and_rounding():
    text = "Equity ended at 104,512.30 after a -12.4% drawdown, with a ratio of 0.4."
    source = {"x": {"equity": 104512.3, "max_drawdown": -0.1238, "ratio": 0.4321}}
    assert verify_numbers({"x": text}, source)["numbers_verified"] == 3
    assert verify_numbers({"x": "The ratio was 0.45."}, source)["numbers_verified"] == 0


def test_verification_ignores_years_that_belong_to_source_dates():
    source = {"summary": {"period_start": "2016-01-04", "n_trades": 5}}
    result = verify_numbers({"summary": "Since 2016, in March 2017, it made 5 trades."}, source)
    assert result["numbers_total"] == 1
    assert result["numbers_verified"] == 1


def completed_row(make_api, report_client: FakeClient):
    client, services = make_api(run_job=None, sandbox=FakeSandbox(), reports=service_with(report_client))
    analysis_id = submit(client).json()["analysis_id"]
    services.job_manager.wait(analysis_id, timeout=WAIT_SECONDS)
    return client, services, analysis_id


def test_report_has_five_sections_and_each_prompt_contains_only_its_slice(make_api):
    report_client = FakeClient()
    client, services, analysis_id = completed_row(make_api, report_client)
    row = services.repository.get_analysis(analysis_id)
    slices = build_slices(row["result"], row["params"], row["model_meta"])

    assert row["status"] == "completed"
    assert [section["id"] for section in row["report"]["sections"]] == list(SECTION_IDS)
    assert row["report"]["status"] == "ok"
    assert row["report"]["model"] == "claude-sonnet-5-5"
    assert len(report_client.calls) == 5
    for call, section_id in zip(report_client.calls, SECTION_IDS):
        assert sent_slice(call) == json.loads(json.dumps(slices[section_id]))
        assert call["tool_choice"] == {"type": "auto"}
        assert call["tools"][0]["strict"] is True
        assert "thinking" not in call
        others = [other for other in SECTION_IDS if other != section_id]
        for other in others:
            assert f"Section id: {other}" not in call["messages"][0]["content"]
    assert "trade_statistics" in json.dumps(sent_slice(report_client.calls[1]))
    assert "trade_statistics" not in json.dumps(sent_slice(report_client.calls[0]))
    assert "global_importance_mean_abs_shap" not in json.dumps(sent_slice(report_client.calls[0]))


def test_model_name_comes_from_configuration(make_api, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_MODEL", "claude-test-model")
    report_client = FakeClient()
    completed_row(make_api, report_client)
    assert {call["model"] for call in report_client.calls} == {"claude-test-model"}


def test_max_tokens_stop_reason_is_a_truncation_error(make_api):
    truncated = FakeClient(lambda section_id, kwargs: tool_response(section_id, "cut", stop_reason="max_tokens"))
    client, services, analysis_id = completed_row(make_api, truncated)
    row = services.repository.get_analysis(analysis_id)
    assert row["status"] == "partial"
    assert row["report"]["status"] == "failed"
    assert row["report"]["error"]["code"] == "report_truncated"
    assert row["result"]["backtest"]["trades"]


@pytest.mark.parametrize("payload", [
    {"id": "summary", "title": "Summary"},
    {"id": "wrong", "title": "T", "text": "x"},
    {"id": "summary", "title": "T", "text": ""},
    "not a dict",
])
def test_invalid_structured_output_is_an_error_not_a_crash(payload):
    client = FakeClient(lambda section_id, kwargs: tool_response(section_id, "", payload=payload))
    report = service_with(client).generate({section_id: {"available": True} for section_id in SECTION_IDS})
    assert report["status"] == "failed"
    assert report["error"]["code"] == "report_invalid_output"


def test_missing_tool_call_is_invalid_output():
    client = FakeClient(lambda section_id, kwargs: SimpleNamespace(stop_reason="end_turn", content=[SimpleNamespace(type="text", text="hi")]))
    report = service_with(client).generate({section_id: {} for section_id in SECTION_IDS})
    assert report["error"]["code"] == "report_invalid_output"


def test_api_failure_and_missing_key_do_not_crash(make_api):
    def raise_connection(section_id, kwargs):
        raise anthropic.APIConnectionError(request=httpx2.Request("POST", "https://api.anthropic.com/v1/messages"))

    report = service_with(FakeClient(raise_connection)).generate({section_id: {} for section_id in SECTION_IDS})
    assert report["error"]["code"] == "report_api_error"

    client, services = make_api(run_job=None, sandbox=FakeSandbox())
    analysis_id = submit(client).json()["analysis_id"]
    services.job_manager.wait(analysis_id, timeout=WAIT_SECONDS)
    row = services.repository.get_analysis(analysis_id)
    assert row["status"] == "partial"
    assert row["report"]["error"]["code"] == "report_api_key_missing"


def test_unavailable_regimes_produce_an_explicit_statement():
    result = {
        "backtest": {"metrics": {"strategy": {}, "benchmark": {}}, "ignored_bar_count": 0},
        "regimes": {"regimes_available": False, "reason": "At least 250 bars are needed; 120 available."},
        "data": {},
    }
    slices = build_slices(result, {}, {})
    assert slices["regimes"]["available"] is False
    assert "unavailable" in slices["regimes"]["instruction"]
    assert slices["regimes"]["reason"].startswith("At least 250")
    assert slices["drivers"]["available"] is False
    client = FakeClient()
    service_with(client).generate(slices)
    assert sent_slice(client.calls[2]) == slices["regimes"]


class ExplodingSandbox(FakeSandbox):
    def __init__(self):
        super().__init__()
        self.armed = False

    def _guard(self):
        if self.armed:
            raise AssertionError("the sandbox must not be called")

    def preflight(self, *args):
        self._guard()
        return super().preflight(*args)

    def predict(self, *args):
        self._guard()
        return super().predict(*args)

    def explain(self, *args):
        self._guard()
        return super().explain(*args)


def test_regenerate_uses_stored_data_and_never_calls_the_sandbox(make_api):
    sandbox = ExplodingSandbox()
    working = FakeClient()
    failing = {"on": True}

    def responder(section_id, kwargs):
        if failing["on"]:
            return tool_response(section_id, "x", stop_reason="max_tokens")
        return working.responder(section_id, kwargs)

    report_client = FakeClient(responder)
    client, services = make_api(run_job=None, sandbox=sandbox, reports=service_with(report_client))
    analysis_id = submit(client).json()["analysis_id"]
    services.job_manager.wait(analysis_id, timeout=WAIT_SECONDS)
    assert services.repository.get_analysis(analysis_id)["status"] == "partial"
    sandbox_calls = list(sandbox.calls)

    sandbox.armed = True
    failing["on"] = False
    response = client.post(f"/analysis/{analysis_id}/report")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert sandbox.calls == sandbox_calls
    row = services.repository.get_analysis(analysis_id)
    assert row["status"] == "completed"
    assert row["error"] is None
    assert row["report"]["status"] == "ok"
    assert row["result"]["stages"]["report"]["state"] == "done"


def test_explain_section_sends_only_that_slice_and_validates_the_id(make_api):
    report_client = FakeClient()
    client, services, analysis_id = completed_row(make_api, report_client)
    report_client.calls.clear()
    row = services.repository.get_analysis(analysis_id)
    slices = build_slices(row["result"], row["params"], row["model_meta"])

    response = client.post(f"/analysis/{analysis_id}/explain-section", json={"section_id": "drivers"})

    assert response.status_code == 200
    assert response.json()["section_id"] == "drivers"
    assert len(report_client.calls) == 1
    assert sent_slice(report_client.calls[0]) == json.loads(json.dumps(slices["drivers"]))
    bad = client.post(f"/analysis/{analysis_id}/explain-section", json={"section_id": "nope"})
    assert bad.status_code == 400
    assert bad.json()["code"] == "invalid_section"


def test_report_endpoints_are_rate_limited_and_need_a_backtest(make_api, monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_RUNS", "2")
    report_client = FakeClient()
    client, services, analysis_id = completed_row(make_api, report_client)
    assert client.post(f"/analysis/{analysis_id}/report").status_code == 200
    assert client.post(f"/analysis/{analysis_id}/explain-section", json={"section_id": "summary"}).status_code == 200
    limited = client.post(f"/analysis/{analysis_id}/report")
    assert limited.status_code == 429
    assert limited.json()["code"] == "rate_limited"

    fresh_client, fresh_services = make_api()
    pending = fresh_services.repository.create_analysis({"status": "queued", "result": None})
    response = fresh_client.post(f"/analysis/{pending['id']}/report")
    assert response.status_code == 409
    assert response.json()["code"] == "analysis_not_ready"


def test_request_uses_auto_tool_choice_strict_tool_and_no_disabled_thinking():
    client = FakeClient()
    service_with(client).generate({section_id: {"available": True} for section_id in SECTION_IDS})
    assert len(client.calls) == 5
    for call in client.calls:
        assert call["tool_choice"] == {"type": "auto"}
        assert call["tools"][0]["strict"] is True
        assert call["tools"][0]["input_schema"]["additionalProperties"] is False
        assert "thinking" not in call
        assert "write_section" in call["system"]
        assert "call the write_section tool" in call["messages"][0]["content"]


def test_text_only_response_is_invalid_output():
    client = FakeClient(lambda section_id, kwargs: SimpleNamespace(
        stop_reason="end_turn",
        content=[SimpleNamespace(type="thinking", thinking=""), SimpleNamespace(type="text", text="Here is the section.")],
    ))
    report = service_with(client).generate({section_id: {} for section_id in SECTION_IDS})
    assert report["status"] == "failed"
    assert report["error"]["code"] == "report_invalid_output"


def test_valid_tool_use_after_a_thinking_block_is_parsed():
    def responder(section_id, kwargs):
        response = tool_response(section_id, f"Text for {section_id}.")
        response.content.insert(0, SimpleNamespace(type="thinking", thinking=""))
        return response

    report = service_with(FakeClient(responder)).generate({section_id: {} for section_id in SECTION_IDS})
    assert report["status"] == "ok"
    assert [section["text"] for section in report["sections"]] == [f"Text for {s}." for s in SECTION_IDS]


def test_default_model_is_claude_sonnet_5_5():
    from app.config import get_settings

    assert get_settings().anthropic_model == "claude-sonnet-5-5"


def constants_result() -> dict:
    return {
        "data": {"ticker": "SPY"},
        "predictions": {"threshold": 0.5},
        "backtest": {
            "initial_capital": 100000.0,
            "fee_bps": 5.0,
            "slippage_bps": 2.0,
            "metrics": {"strategy": {}, "benchmark": {}},
            "ignored_bar_count": 0,
        },
        "regimes": {
            "regimes_available": True,
            "n_states": 3,
            "time_in_regime_pct": {},
            "n_bars": {},
            "performance": {},
        },
        "shap": {
            "explained_output": "probability",
            "explainer": "tree",
            "sample_size": 412,
            "feature_names": ["rsi_14", "vol_20d", "ret_1d"],
            "feature_importance": {"rsi_14": 0.1, "vol_20d": 0.05, "ret_1d": 0.02},
            "feature_importance_by_regime": None,
        },
    }


def test_slices_expose_model_and_method_constants():
    slices = build_slices(constants_result(), {"fee_bps": 5.0, "slippage_bps": 2.0}, {})
    expected_costs = {
        "annualization_days": 252,
        "signal_threshold": 0.5,
        "fee_bps": 5.0,
        "slippage_bps": 2.0,
        "initial_capital": 100000.0,
    }
    assert slices["summary"]["constants"] == expected_costs
    assert slices["performance"]["constants"] == {**expected_costs, "var_confidence": 0.95}
    assert slices["regimes"]["constants"] == {"n_states": 3}
    assert slices["drivers"]["constants"] == {"n_features": 3, "sample_size": 412}


def test_var_confidence_is_the_value_used_by_the_metrics_code():
    from app.backtest import metrics
    from app.regime.hmm_detector import N_REGIMES
    from app.pipeline.signals import PROBABILITY_THRESHOLD

    slices = build_slices(constants_result(), {}, {})
    assert slices["performance"]["constants"]["var_confidence"] == metrics.VAR_CONFIDENCE
    assert metrics.VAR_PERCENTILE == round((1 - metrics.VAR_CONFIDENCE) * 100)
    assert slices["performance"]["constants"]["annualization_days"] == metrics.TRADING_DAYS_PER_YEAR
    assert slices["summary"]["constants"]["signal_threshold"] == PROBABILITY_THRESHOLD
    assert slices["regimes"]["constants"]["n_states"] == N_REGIMES


def test_verification_accepts_quoted_constants_only_when_present_in_the_source():
    slices = build_slices(constants_result(), {}, {})
    regimes = verify_numbers({"regimes": "Regimes come from a Gaussian HMM with 3 states."}, slices)
    performance = verify_numbers({"performance": "The daily 95% value at risk is reported."}, slices)
    assert regimes["numbers_verified"] == regimes["numbers_total"] == 1
    assert performance["numbers_verified"] == performance["numbers_total"] == 1

    without = dict(slices["performance"], constants={k: v for k, v in slices["performance"]["constants"].items() if k != "var_confidence"})
    rejected = verify_numbers({"performance": "The daily 95% value at risk is reported."}, {"performance": without})
    assert rejected["numbers_verified"] == 0
    assert rejected["sections"]["performance"]["unverified"][0]["number"] == "95%"


def test_prompt_allows_quoting_constants():
    from app.reports.prompts import SYSTEM_PROMPT

    assert '"constants"' in SYSTEM_PROMPT


def test_slices_expose_parameters_of_selected_catalog_indicators():
    from app.data.indicators import CATALOG

    params = {"data_source_kind": "ticker", "feature_ids": ["rsi_14", "macd_hist", "sma_ratio_20_50"]}
    slices = build_slices(constants_result(), params, {})
    expected = {feature_id: dict(CATALOG[feature_id].parameters) for feature_id in params["feature_ids"]}
    assert expected["rsi_14"] == {"period": 14}
    assert expected["macd_hist"] == {"fast_span": 12, "slow_span": 26, "signal_span": 9}
    assert expected["sma_ratio_20_50"] == {"fast_window": 20, "slow_window": 50}
    for section_id in ("summary", "performance", "regimes", "drivers"):
        assert slices[section_id]["constants"]["indicator_parameters"] == expected


def test_every_catalog_indicator_declares_its_parameters():
    from app.data.indicators import CATALOG

    for indicator in CATALOG.values():
        assert indicator.parameters
        assert all(isinstance(value, int) and value > 0 for value in indicator.parameters.values())


def test_csv_features_add_no_indicator_parameters():
    params = {"data_source_kind": "csv", "feature_ids": ["rsi_14", "my_feature"]}
    slices = build_slices(constants_result(), params, {})
    assert "indicator_parameters" not in slices["drivers"]["constants"]


def test_verification_accepts_indicator_parameters_but_still_flags_unknown_numbers():
    params = {"data_source_kind": "ticker", "feature_ids": ["ema_ratio_12_26", "sma_ratio_20_50", "rsi_14"]}
    slices = build_slices(constants_result(), params, {})
    text = "The EMA 12/26 ratio, the SMA 20/50 ratio and the 14-bar RSI lead the ranking."
    report = verify_numbers({"drivers": text}, slices)
    assert report["numbers_total"] == 5
    assert report["numbers_verified"] == 5

    flagged = verify_numbers({"drivers": "A 37-bar lookback is also used."}, slices)
    assert flagged["numbers_verified"] == 0
    assert flagged["sections"]["drivers"]["unverified"][0]["number"] == "37"

    without = verify_numbers({"drivers": text}, build_slices(constants_result(), {}, {}))
    assert without["flagged"] is True
