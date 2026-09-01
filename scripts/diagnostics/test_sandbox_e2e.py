import pickle
import numpy as np
import pandas as pd
from sklearn.tree import DecisionTreeClassifier
from app.models.wrapper import ModelMetadata, SignalType
from app.models.validation import register_model
from app.sandbox.runner import run_predict_in_sandbox
from app.backtest.engine import run_backtest
from app.regime.hmm_detector import detect_regimes
from app.explainability.shap_engine import compute_shap_explanation, compute_global_feature_importance
from app.reports.generator import assemble_report_data, generate_full_report, generate_section_explanation


def build_synthetic_ohlcv(n: int = 300) -> pd.DataFrame:
    np.random.seed(1)
    timestamps = pd.date_range("2024-01-01", periods=n, freq="D", tz="UTC")

    prices = [100.0]
    for i in range(1, n):
        if i < n // 3:
            drift = 0.6
            noise_std = 0.3
        elif i < 2 * n // 3:
            drift = -0.6
            noise_std = 0.3
        else:
            drift = 0.0
            noise_std = 1.2
        shock = np.random.normal(drift, noise_std)
        prices.append(max(prices[-1] + shock, 1.0))

    close = np.array(prices)
    open_ = close + np.random.normal(0, 0.1, n)
    high = np.maximum(open_, close) + np.abs(np.random.normal(0, 0.15, n))
    low = np.minimum(open_, close) - np.abs(np.random.normal(0, 0.15, n))
    volume = np.random.uniform(900, 1300, n)

    return pd.DataFrame({
        "timestamp": timestamps,
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume,
    })


def main():
    X_train = pd.DataFrame({
        "open": [100.0, 100.0, 50.0, 80.0, 80.0],
        "close": [105.0, 95.0, 50.0, 85.0, 75.0],
    })
    y_train = [1, -1, -1, 1, -1]

    model = DecisionTreeClassifier(max_depth=2, random_state=0)
    model.fit(X_train, y_train)
    model_bytes = pickle.dumps(model)

    metadata = ModelMetadata(
        name="dummy_decision_tree",
        signal_type=SignalType.DISCRETE,
        expected_columns=["open", "close"],
    )
    registered = register_model(metadata, model_bytes, "dummy_model.pkl")
    print("Model registered:", registered.id)

    ohlcv = build_synthetic_ohlcv()
    features = ohlcv[["open", "close"]]
    records = features.to_dict(orient="records")

    sandbox_result = run_predict_in_sandbox(registered.storage_path, records, "discrete")

    backtest_result = run_backtest(
        ohlcv=ohlcv,
        features=features,
        signals=sandbox_result["predictions"],
        signal_type="discrete",
    )
    print("Trade count:", backtest_result["trade_count"])
    print("Total PnL:", backtest_result["total_pnl"])

    regime_result = detect_regimes(ohlcv)
    print("Time in regime (%):", regime_result["time_in_regime_pct"])

    sample = features.sample(n=30, random_state=0)
    background_records = features.sample(n=50, random_state=1).to_dict(orient="records")
    explanation = compute_shap_explanation(
        model_storage_path=registered.storage_path,
        records=sample.to_dict(orient="records"),
        background_records=background_records,
    )
    feature_importance = compute_global_feature_importance(
        explanation["shap_values"], explanation["feature_names"]
    )
    print("Feature importance:", feature_importance)

    report_data = assemble_report_data(
        model_name=registered.name,
        ohlcv=ohlcv,
        trades=backtest_result["trades"],
        feature_importance=feature_importance,
        regime_result=regime_result,
    )
    print("\n--- Report data assembled ---")
    print(report_data)

    print("\n--- Generating full report ---")
    report_text = generate_full_report(report_data)
    print(report_text)

    print("\n--- Generating section explanation (regime behavior) ---")
    section_explanation = generate_section_explanation(
        "Behavior by Market Regime",
        {
            "regime_behavior": report_data["regime_behavior"],
            "time_in_regime_pct": report_data["time_in_regime_pct"],
        },
    )
    print(section_explanation)


if __name__ == "__main__":
    main()