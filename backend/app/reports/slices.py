from app.backtest.metrics import TRADING_DAYS_PER_YEAR, VAR_CONFIDENCE
from app.data.indicators import CATALOG
from app.regime.hmm_detector import REGIME_NAMES

SECTION_IDS = ("summary", "performance", "regimes", "drivers", "risks")
SECTION_TITLES = {
    "summary": "Summary",
    "performance": "Performance",
    "regimes": "Market regimes",
    "drivers": "What drives the model",
    "risks": "Risks and limitations",
}
FLOAT_DECIMALS = 4
HEADLINE_METRICS = ("total_return", "cagr", "sharpe", "max_drawdown", "annualized_volatility", "n_trades", "win_rate")
TRADE_METRICS = (
    "n_trades", "n_long", "n_short", "win_rate", "profit_factor", "avg_win", "avg_loss", "best_trade",
    "worst_trade", "avg_bars_held", "time_in_market_long", "time_in_market_short", "round_trips_per_year",
    "total_costs_pct_of_initial", "sortino", "calmar", "var_95_daily", "best_day", "worst_day",
    "longest_drawdown_days", "correlation_to_benchmark", "beta_to_benchmark",
)


def round_numbers(value):
    if isinstance(value, bool) or value is None or isinstance(value, (str, int)):
        return value
    if isinstance(value, float):
        return round(value, FLOAT_DECIMALS)
    if isinstance(value, dict):
        return {key: round_numbers(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [round_numbers(item) for item in value]
    return value


def unavailable(subject: str, reason: str | None) -> dict:
    return {
        "available": False,
        "reason": reason or f"{subject} could not be computed.",
        "instruction": f"State explicitly that {subject} is unavailable for this analysis and why. Do not describe it.",
    }


def indicator_parameters(params: dict) -> dict:
    if params.get("data_source_kind") == "csv":
        return {}
    return {
        feature_id: dict(CATALOG[feature_id].parameters)
        for feature_id in params.get("feature_ids") or []
        if feature_id in CATALOG
    }


def with_indicator_parameters(constants: dict, params: dict) -> dict:
    parameters = indicator_parameters(params)
    return {**constants, "indicator_parameters": parameters} if parameters else constants


def backtest_constants(result: dict, params: dict) -> dict:
    backtest = result.get("backtest", {})
    return {
        "annualization_days": TRADING_DAYS_PER_YEAR,
        "signal_threshold": (result.get("predictions") or {}).get("threshold"),
        "fee_bps": params.get("fee_bps", backtest.get("fee_bps")),
        "slippage_bps": params.get("slippage_bps", backtest.get("slippage_bps")),
        "initial_capital": backtest.get("initial_capital"),
    }


def summary_slice(result: dict, params: dict, model_meta: dict) -> dict:
    metrics = result["backtest"]["metrics"]
    data = result.get("data", {})
    return {
        "ticker": data.get("ticker"),
        "period_start": data.get("effective_start"),
        "period_end": data.get("end"),
        "model_family": model_meta.get("family"),
        "explained_output": model_meta.get("explained_output"),
        "strategy": {key: metrics["strategy"].get(key) for key in HEADLINE_METRICS},
        "benchmark_buy_and_hold": {key: metrics["benchmark"].get(key) for key in HEADLINE_METRICS},
        "constants": with_indicator_parameters(backtest_constants(result, params), params),
    }


def performance_slice(result: dict, params: dict, model_meta: dict) -> dict:
    strategy = result["backtest"]["metrics"]["strategy"]
    return {
        "trade_statistics": {key: strategy.get(key) for key in TRADE_METRICS},
        "fee_bps": params.get("fee_bps"),
        "slippage_bps": params.get("slippage_bps"),
        "constants": with_indicator_parameters({**backtest_constants(result, params), "var_confidence": VAR_CONFIDENCE}, params),
    }


def regimes_slice(result: dict, params: dict, model_meta: dict) -> dict:
    regimes = result.get("regimes")
    if not regimes or not regimes.get("regimes_available"):
        return unavailable("market regime analysis", regimes.get("reason") if regimes else None)
    performance = regimes.get("performance") or {}
    return {
        "available": True,
        "in_sample": True,
        "model": f"Gaussian HMM, {regimes.get('n_states')} states, filtered probabilities",
        "constants": with_indicator_parameters({"n_states": regimes.get("n_states")}, params),
        "regimes": {
            name: {
                "share_of_bars": regimes["time_in_regime_pct"].get(name),
                "n_bars": regimes["n_bars"].get(name),
                "strategy_return": performance.get(name, {}).get("strategy_return"),
                "n_trades": performance.get(name, {}).get("n_trades"),
                "win_rate": performance.get(name, {}).get("win_rate"),
            }
            for name in REGIME_NAMES
        },
    }


def drivers_slice(result: dict, params: dict, model_meta: dict) -> dict:
    shap = result.get("shap")
    if not shap:
        return unavailable("the SHAP explanation", None)
    ranked = sorted(shap["feature_importance"].items(), key=lambda item: item[1], reverse=True)
    by_regime = shap.get("feature_importance_by_regime")
    return {
        "available": True,
        "explained_output": shap.get("explained_output"),
        "explainer": shap.get("explainer"),
        "sample_size": shap.get("sample_size"),
        "global_importance_mean_abs_shap": dict(ranked),
        "importance_by_regime": None if by_regime is None else {
            name: {
                "n_rows": item["n_rows"],
                "low_sample": item["low_sample"],
                "importance": item["importance"],
            }
            for name, item in by_regime.items()
        },
        "regimes_available": by_regime is not None,
        "constants": with_indicator_parameters(
            {"n_features": len(shap.get("feature_names") or shap["feature_importance"]), "sample_size": shap.get("sample_size")},
            params,
        ),
    }


def risks_slice(result: dict, params: dict, model_meta: dict) -> dict:
    data = result.get("data", {})
    shap = result.get("shap") or {}
    regimes = result.get("regimes") or {}
    return {
        "data_source": data.get("data_source"),
        "ignored_bar_count": result.get("backtest", {}).get("ignored_bar_count"),
        "invalid_count": data.get("invalid_count"),
        "warmup_dropped": data.get("warmup_dropped"),
        "requested_start": data.get("requested_start"),
        "effective_start": data.get("effective_start"),
        "regimes_in_sample": bool(regimes.get("regimes_available")),
        "regimes_available": bool(regimes.get("regimes_available")),
        "shap_available": bool(shap),
        "shap_sampling": shap.get("sampling"),
        "flags": [
            "Backtest on historical data; past behaviour does not predict future results.",
            "The HMM is fitted on the full history (in-sample); labels use filtered probabilities.",
            "SHAP describes the model, not causality; correlated features share credit.",
        ],
        "instruction": "This section needs no numbers. Describe the limitations and flags qualitatively.",
    }


SLICE_BUILDERS = {
    "summary": summary_slice,
    "performance": performance_slice,
    "regimes": regimes_slice,
    "drivers": drivers_slice,
    "risks": risks_slice,
}


def build_slices(result: dict, params: dict, model_meta: dict) -> dict:
    return {section_id: round_numbers(SLICE_BUILDERS[section_id](result, params, model_meta)) for section_id in SECTION_IDS}
