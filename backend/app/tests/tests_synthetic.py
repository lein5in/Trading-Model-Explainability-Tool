import os
import pickle
import tempfile
import numpy as np
import pandas as pd
from sklearn.tree import DecisionTreeClassifier
from app.explainability.shap_engine import ShapConfig, compute_shap

N_ROWS = 300
RSI_THRESHOLD = 50.0


def build_rsi_only_frame(seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    return pd.DataFrame({
        "date": pd.date_range("2020-01-01", periods=N_ROWS, freq="D").strftime("%Y-%m-%d"),
        "rsi_14": rng.uniform(0, 100, N_ROWS),
        "noise_feature": rng.uniform(0, 100, N_ROWS),
    })


def build_rsi_only_model(frame: pd.DataFrame) -> DecisionTreeClassifier:
    features = frame[["rsi_14", "noise_feature"]]
    labels = (frame["rsi_14"] > RSI_THRESHOLD).astype(int)
    return DecisionTreeClassifier(max_depth=3, random_state=0).fit(features, labels)


def run_single_feature_sanity_check() -> dict:
    frame = build_rsi_only_frame()
    model = build_rsi_only_model(frame)
    with tempfile.TemporaryDirectory() as work_dir:
        model_path = os.path.join(work_dir, "synthetic_rsi_only.pkl")
        with open(model_path, "wb") as f:
            f.write(pickle.dumps(model))
        explanation = compute_shap(
            model_path,
            frame,
            ["rsi_14", "noise_feature"],
            list(range(N_ROWS)),
            None,
            [],
            ShapConfig(sample_size=100),
            timeout_seconds=180,
        )["shap"]
    importance = explanation["feature_importance"]
    total = sum(importance.values())
    rsi_share = importance["rsi_14"] / total if total > 0 else 0.0
    return {
        "passed": rsi_share > 0.9,
        "rsi_share": rsi_share,
        "importance": importance,
        "max_additivity_gap": explanation["max_additivity_gap"],
        "explainer": explanation["explainer"],
    }
