"""GMS 信号追溯：日/周 timeframe 路由辅助逻辑。"""

from types import SimpleNamespace

from backend_api.stock import gms_trace_routes as routes


def test_normalize_timeframe():
    assert routes._normalize_timeframe(None) == "daily"
    assert routes._normalize_timeframe("weekly") == "weekly"
    assert routes._normalize_timeframe("WEEKLY") == "weekly"
    assert routes._normalize_timeframe("bogus") == "daily"


def test_resolve_trace_and_mfr_models():
    assert routes._resolve_trace_model("daily") is routes.GMSSignalTrace
    assert routes._resolve_trace_model("weekly") is routes.GMSSignalTraceWeekly
    assert routes._resolve_mfr_model("daily") is routes.MeanFrequencyResonanceIndicators
    assert (
        routes._resolve_mfr_model("weekly")
        is routes.MeanFrequencyResonanceIndicatorsWeekly
    )


def test_recompute_request_defaults_daily():
    body = routes.GmsTraceRecomputeRequest(code="000423")
    assert routes._normalize_timeframe(body.timeframe) == "daily"


def test_config_display_still_works():
    row = SimpleNamespace(id=9, name="default_weekly", version_label="周线标准版")
    assert "周线" in routes._config_display_name(row) or "default_weekly" in routes._config_display_name(row)
