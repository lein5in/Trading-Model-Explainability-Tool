from dataclasses import dataclass
import numpy as np
import pandas as pd
from app.regime.hmm_detector import REGIME_NAMES
from app.sandbox.runner import SandboxExecutionError, run_explain_in_sandbox

CONTRIBUTION_DECIMALS = 6
VALUE_DECIMALS = 6


@dataclass(frozen=True)
class ShapConfig:
    sample_size: int = 600
    min_rows_per_regime: int = 30
    low_sample_threshold: int = 100
    max_trade_rows: int = 200
    background_rows: int = 100
    kernel_nsamples: int = 200
    kernel_background_size: int = 10
    epsilon: float = 0.01
    seed: int = 0


class ShapStageError(Exception):
    def __init__(self, code: str, message: str, details: dict | None = None):
        super().__init__(message)
        self.code = code
        self.details = details or {}


def allocate(group_sizes: dict[int, int], sample_size: int, min_per_group: int) -> dict[int, int]:
    total = sum(group_sizes.values())
    if total <= sample_size:
        return dict(group_sizes)
    min_per_group = min(min_per_group, sample_size // len(group_sizes))
    exact = {group: sample_size * size / total for group, size in group_sizes.items()}
    allocation = {group: min(size, max(int(exact[group]), min_per_group)) for group, size in group_sizes.items()}
    while sum(allocation.values()) > sample_size:
        reducible = [g for g in allocation if allocation[g] > min(min_per_group, group_sizes[g])]
        if not reducible:
            break
        largest = max(reducible, key=lambda g: allocation[g])
        allocation[largest] -= 1
    by_remainder = sorted(group_sizes, key=lambda g: exact[g] - int(exact[g]), reverse=True)
    while sum(allocation.values()) < sample_size:
        progressed = False
        for group in by_remainder:
            if sum(allocation.values()) >= sample_size:
                break
            if allocation[group] < group_sizes[group]:
                allocation[group] += 1
                progressed = True
        if not progressed:
            break
    return allocation


def stratified_sample(
    eligible_positions: list[int],
    regime_index_per_bar: list | None,
    sample_size: int,
    min_per_regime: int,
    seed: int,
) -> list[int]:
    rng = np.random.default_rng(seed)
    eligible = sorted(eligible_positions)
    if regime_index_per_bar is None:
        if len(eligible) <= sample_size:
            return eligible
        return sorted(int(p) for p in rng.choice(eligible, size=sample_size, replace=False))
    groups: dict[int, list[int]] = {}
    for position in eligible:
        regime = regime_index_per_bar[position]
        if regime is not None:
            groups.setdefault(int(regime), []).append(position)
    allocation = allocate({g: len(p) for g, p in groups.items()}, sample_size, min_per_regime)
    chosen = []
    for group, positions in groups.items():
        count = allocation[group]
        picked = positions if count >= len(positions) else rng.choice(positions, size=count, replace=False)
        chosen.extend(int(p) for p in picked)
    return sorted(chosen)


def mean_abs_importance(values: np.ndarray, feature_names: list[str]) -> dict:
    means = np.abs(values).mean(axis=0)
    return {name: float(score) for name, score in zip(feature_names, means)}


def importance_by_regime(values: np.ndarray, sample_regimes: list, feature_names: list[str], low_sample_threshold: int) -> dict:
    result = {}
    for index, name in enumerate(REGIME_NAMES):
        mask = np.array([regime == index for regime in sample_regimes], dtype=bool)
        n_rows = int(mask.sum())
        result[name] = {
            "n_rows": n_rows,
            "low_sample": n_rows < low_sample_threshold,
            "importance": mean_abs_importance(values[mask], feature_names) if n_rows > 0 else None,
        }
    return result


def rounded(values, decimals: int) -> list:
    return [round(float(v), decimals) for v in values]


def trade_rows_for(trades: list[dict], eligible: set[int], max_rows: int) -> list[dict]:
    selected = []
    for trade in trades:
        if len(selected) >= max_rows:
            break
        if trade.get("signal_bar_index") in eligible:
            selected.append(trade)
    return selected


def compute_shap(
    model_path: str,
    frame: pd.DataFrame,
    feature_columns: list[str],
    eligible_positions: list[int],
    regimes: dict | None,
    trades: list[dict],
    config: ShapConfig,
    timeout_seconds: float,
    run_explain=run_explain_in_sandbox,
) -> dict:
    regimes_available = bool(regimes and regimes.get("regimes_available"))
    regime_index_per_bar = regimes["regime_index_per_bar"] if regimes_available else None
    eligible = sorted(eligible_positions)
    if not eligible:
        raise ShapStageError("shap_no_rows", "No bar has finite features and a signal to explain.")

    sample_positions = stratified_sample(eligible, regime_index_per_bar, config.sample_size, config.min_rows_per_regime, config.seed)
    rng = np.random.default_rng(config.seed + 1)
    background_positions = eligible if len(eligible) <= config.background_rows else sorted(
        int(p) for p in rng.choice(eligible, size=config.background_rows, replace=False)
    )
    selected_trades = trade_rows_for(trades, set(eligible), config.max_trade_rows)
    trade_positions = [trade["signal_bar_index"] for trade in selected_trades]

    matrix = frame[feature_columns].to_numpy(dtype=float)
    payload = {
        "feature_names": feature_columns,
        "global_rows": matrix[sample_positions].tolist(),
        "trade_rows": matrix[trade_positions].tolist() if trade_positions else [],
        "background_rows": matrix[background_positions].tolist(),
        "epsilon": config.epsilon,
        "nsamples": config.kernel_nsamples,
        "kernel_background_size": config.kernel_background_size,
    }
    try:
        result = run_explain(model_path, payload, timeout_seconds)
    except SandboxExecutionError as exc:
        if exc.code == "shap_additivity_failed":
            raise ShapStageError("shap_additivity_failed", str(exc), {"max_gap": exc.details.get("max_gap"), "epsilon": config.epsilon})
        raise

    global_values = np.asarray(result["global_values"], dtype=float).reshape(len(sample_positions), len(feature_columns))
    trade_values = np.asarray(result["trade_values"], dtype=float).reshape(len(trade_positions), len(feature_columns))
    sample_regimes = [regime_index_per_bar[p] for p in sample_positions] if regimes_available else [None] * len(sample_positions)
    dates = frame["date"].tolist()

    trade_rows = []
    trade_row_index = {}
    for row_index, (trade, position) in enumerate(zip(selected_trades, trade_positions)):
        trade_row_index[trade["id"]] = row_index
        trade_rows.append({
            "trade_id": trade["id"],
            "bar_index": position,
            "date": dates[position],
            "base_value": float(result["base_value"]),
            "output": float(result["trade_outputs"][row_index]),
            "contributions": dict(zip(feature_columns, rounded(trade_values[row_index], CONTRIBUTION_DECIMALS))),
            "feature_values": dict(zip(feature_columns, rounded(matrix[position], VALUE_DECIMALS))),
        })

    shap_result = {
        "explainer": result["explainer"],
        "explained_output": result["explained_output"],
        "explained_class": result["explained_class"],
        "base_value": float(result["base_value"]),
        "max_additivity_gap": float(result["max_additivity_gap"]),
        "additivity_epsilon": config.epsilon,
        "feature_names": feature_columns,
        "sampling": "stratified_by_regime" if regimes_available else "uniform",
        "sample_size": len(sample_positions),
        "feature_importance": mean_abs_importance(global_values, feature_columns),
        "feature_importance_by_regime": importance_by_regime(global_values, sample_regimes, feature_columns, config.low_sample_threshold) if regimes_available else None,
        "low_sample_threshold": config.low_sample_threshold,
        "sample": {
            "bar_index": sample_positions,
            "date": [dates[p] for p in sample_positions],
            "regime": [REGIME_NAMES[r] if r is not None else None for r in sample_regimes],
            "output": rounded(result["global_outputs"], VALUE_DECIMALS),
            "feature_values": [rounded(matrix[p], VALUE_DECIMALS) for p in sample_positions],
            "contributions": [rounded(row, CONTRIBUTION_DECIMALS) for row in global_values],
        },
        "trade_rows": trade_rows,
        "trade_rows_capped": len(selected_trades) < sum(1 for t in trades if t.get("signal_bar_index") in set(eligible)),
    }
    return {"shap": shap_result, "trade_row_index": trade_row_index}
