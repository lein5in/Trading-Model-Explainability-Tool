import time
from dataclasses import dataclass, field
import numpy as np
from app.backtest.engine import run_backtest
from app.config import Settings
from app.data.csv_input import CsvValidationError, parse_csv
from app.data.dataset import DatasetError, build_catalog_dataset, build_csv_dataset, extended_start
from app.data.ingestion import DataUnavailableError, fetch_ohlcv
from app.explainability.shap_engine import ShapConfig, ShapStageError, compute_shap
from app.pipeline.jobs import AnalysisJob
from app.pipeline.signals import outputs_to_signals, signal_rule
from app.regime.hmm_detector import REGIME_NAMES, RegimeDetectionError, detect_regimes
from app.sandbox.runner import SandboxExecutionError, SandboxTimeoutError

STAGES = ("validate", "predict", "backtest", "regimes", "shap", "report")
FATAL_STAGES = ("validate", "predict", "backtest")
UNLIMITED = 10 ** 9


class StageFailure(Exception):
    def __init__(self, code: str, message: str, details: dict | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


class JobTimeout(Exception):
    pass


@dataclass
class PipelineDeps:
    repository: object
    sandbox: object
    report_generator: object


@dataclass
class JobState:
    job: AnalysisJob
    deps: PipelineDeps
    settings: Settings
    deadline: float
    clock: object = time.monotonic
    result: dict = field(default_factory=dict)
    model_meta: dict = field(default_factory=dict)
    errors: list = field(default_factory=list)
    report: dict | None = None
    frame: object = None
    requested_features: list = field(default_factory=list)
    column_order: list = field(default_factory=list)
    eligible: list = field(default_factory=list)
    outputs: object = None
    signals: list = field(default_factory=list)
    backtest: dict | None = None
    regimes: dict | None = None

    def remaining(self) -> float:
        remaining = self.deadline - self.clock()
        if remaining <= 0:
            raise JobTimeout()
        return remaining


def load_dataset(job: AnalysisJob, repository) -> dict:
    params = job.params
    if params["data_source_kind"] == "csv":
        with open(job.csv_path, "rb") as f:
            parsed = parse_csv(f.read(), max_rows=UNLIMITED, max_features=UNLIMITED)
        dataset = build_csv_dataset(parsed, params.get("start_date"), params.get("end_date"))
        dataset.update({"invalid_count": parsed["invalid_count"], "data_source": "csv"})
        return dataset
    fetch_start = extended_start(params["start_date"], params["feature_ids"])
    ingestion = fetch_ohlcv(params["ticker"], fetch_start, params["end_date"], repository)
    dataset = build_catalog_dataset(ingestion["data"], params["feature_ids"], params["start_date"], params["end_date"])
    dataset.update({"invalid_count": ingestion["invalid_count"], "data_source": ingestion["data_source"]})
    return dataset


def finite_rows(matrix: np.ndarray) -> list[int]:
    return [int(p) for p in np.flatnonzero(np.isfinite(matrix).all(axis=1))]


def sandbox_failure(code: str, exc: SandboxExecutionError) -> StageFailure:
    details = {"reason": exc.code}
    details.update(exc.details or {})
    return StageFailure(code, str(exc), details)


def validate_stage(state: JobState) -> None:
    job = state.job
    try:
        dataset = load_dataset(job, state.deps.repository)
    except DataUnavailableError as exc:
        raise StageFailure(exc.code, str(exc), {"ticker": exc.ticker})
    except DatasetError as exc:
        raise StageFailure(exc.code, str(exc))
    except CsvValidationError as exc:
        raise StageFailure(exc.code, str(exc), exc.details)

    frame = dataset["frame"]
    requested = list(dataset["feature_columns"])
    matrix = frame[requested].to_numpy(dtype=float)
    eligible = finite_rows(matrix)
    if not eligible:
        raise StageFailure("insufficient_data", "No bar has every feature defined.")

    preflight_rows = matrix[eligible[: state.settings.preflight_rows]].tolist()
    try:
        preflight = state.deps.sandbox.preflight(job.model_path, requested, preflight_rows, state.remaining())
    except SandboxTimeoutError:
        raise
    except SandboxExecutionError as exc:
        raise sandbox_failure("preflight_failed", exc)

    state.frame = frame
    state.requested_features = requested
    state.column_order = list(preflight["column_order"])
    state.eligible = eligible
    state.model_meta.update({
        "signal_type": preflight["signal_type"],
        "family": preflight["family"],
        "model_class": preflight["model_class"],
        "explained_output": preflight["explained_output"],
        "explained_class": preflight["explained_class"],
        "feature_columns": state.column_order,
        "columns_reordered": bool(preflight.get("reordered")),
    })
    state.result["data"] = {
        "ticker": job.params.get("ticker"),
        "data_source": dataset["data_source"],
        "invalid_count": int(dataset["invalid_count"]),
        "warmup_dropped": int(dataset["warmup_dropped"]),
        "requested_start": dataset["requested_start"],
        "effective_start": dataset["effective_start"],
        "end": dataset["end"],
        "n_bars": len(frame),
        "feature_columns": state.column_order,
    }
    state.result["bars"] = {column: frame[column].tolist() for column in ["date", "open", "high", "low", "close", "volume"]}


def predict_stage(state: JobState) -> None:
    rows = state.frame[state.column_order].to_numpy(dtype=float)[state.eligible].tolist()
    try:
        predicted = state.deps.sandbox.predict(state.job.model_path, state.column_order, rows, state.remaining())
    except SandboxTimeoutError:
        raise
    except SandboxExecutionError as exc:
        raise sandbox_failure("predict_failed", exc)

    values = np.array([np.nan if v is None else float(v) for v in predicted["outputs"]], dtype=float)
    if len(values) != len(state.eligible):
        raise StageFailure("predict_failed", f"The model returned {len(values)} outputs for {len(state.eligible)} rows.")
    outputs = np.full(len(state.frame), np.nan)
    outputs[state.eligible] = values
    signal_type = state.model_meta["signal_type"]
    dead_zone = state.settings.continuous_signal_dead_zone
    state.outputs = outputs
    state.signals = outputs_to_signals(outputs, signal_type, dead_zone)
    state.result["predictions"] = {
        "output": outputs.tolist(),
        "signal": state.signals,
        "signal_type": signal_type,
        "explained_output": state.model_meta["explained_output"],
        "skipped_bars": len(state.frame) - len(state.eligible),
        "nan_outputs": int(np.isnan(values).sum()),
        **signal_rule(signal_type, state.model_meta["explained_output"], dead_zone),
    }


def backtest_stage(state: JobState) -> None:
    params = state.job.params
    try:
        state.backtest = run_backtest(state.frame, state.signals, params["fee_bps"], params["slippage_bps"])
    except Exception as exc:
        raise StageFailure("backtest_failed", f"{type(exc).__name__}: {exc}")
    for trade in state.backtest["trades"]:
        trade["shap_row_index"] = None
    state.result["backtest"] = state.backtest


def regime_performance(regimes: dict, backtest: dict) -> dict:
    equity = np.array([point["equity"] for point in backtest["equity_curve"]], dtype=float)
    daily = np.concatenate([[0.0], equity[1:] / equity[:-1] - 1.0]) if len(equity) else np.array([])
    labels = regimes["regime_per_bar"]
    performance = {}
    for name in REGIME_NAMES:
        mask = np.array([label == name for label in labels], dtype=bool)
        trades = [trade for trade in backtest["trades"] if trade.get("regime") == name]
        wins = [trade for trade in trades if trade["pnl"] > 0]
        performance[name] = {
            "n_bars": int(mask.sum()),
            "share": regimes["time_in_regime_pct"].get(name),
            "strategy_return": float(np.prod(1.0 + daily[mask]) - 1.0) if mask.any() else None,
            "n_trades": len(trades),
            "win_rate": len(wins) / len(trades) if trades else None,
        }
    return performance


def regimes_stage(state: JobState) -> None:
    try:
        regimes = detect_regimes(state.frame)
    except RegimeDetectionError as exc:
        raise StageFailure("regimes_failed", str(exc))
    state.regimes = regimes
    if regimes["regimes_available"]:
        for trade in state.backtest["trades"]:
            signal_bar = trade["signal_bar_index"]
            trade["regime"] = regimes["regime_per_bar"][signal_bar] if 0 <= signal_bar < len(regimes["regime_per_bar"]) else None
        regimes["performance"] = regime_performance(regimes, state.backtest)
    else:
        regimes["performance"] = None
    state.result["regimes"] = regimes


def shap_config(settings: Settings) -> ShapConfig:
    return ShapConfig(
        sample_size=settings.shap_sample_size,
        min_rows_per_regime=settings.shap_min_rows_per_regime,
        low_sample_threshold=settings.shap_low_sample_threshold,
        max_trade_rows=settings.shap_max_trade_rows,
        background_rows=settings.shap_background_rows,
        kernel_nsamples=settings.shap_kernel_nsamples,
        kernel_background_size=settings.shap_kernel_background_size,
    )


def shap_stage(state: JobState) -> None:
    explainable = [p for p in state.eligible if np.isfinite(state.outputs[p])]
    try:
        output = compute_shap(
            state.job.model_path,
            state.frame,
            state.column_order,
            explainable,
            state.regimes,
            state.backtest["trades"],
            shap_config(state.settings),
            state.remaining(),
            run_explain=state.deps.sandbox.explain,
        )
    except SandboxTimeoutError:
        raise
    except ShapStageError as exc:
        raise StageFailure(exc.code, str(exc), exc.details)
    except SandboxExecutionError as exc:
        raise sandbox_failure("shap_failed", exc)
    for trade in state.backtest["trades"]:
        trade["shap_row_index"] = output["trade_row_index"].get(trade["id"])
    state.result["shap"] = output["shap"]


def report_stage(state: JobState) -> None:
    report = state.deps.report_generator(state)
    state.report = report
    if report.get("status") != "ok":
        error = report.get("error") or {}
        raise StageFailure(error.get("code", "report_failed"), error.get("message", "The report could not be generated."))


STAGE_FUNCTIONS = {
    "validate": validate_stage,
    "predict": predict_stage,
    "backtest": backtest_stage,
    "regimes": regimes_stage,
    "shap": shap_stage,
    "report": report_stage,
}
