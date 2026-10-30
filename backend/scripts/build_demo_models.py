import json
import subprocess
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
OUTPUT_DIR = BACKEND_DIR / "app" / "demo_models"
SANDBOX_IMAGE = "trading-explainability-sandbox"
CONTAINER_REPO = "/repo"
CONTAINER_OUTPUT = "/out"
INSIDE_FLAG = "--inside"
FEATURES = ["rsi_14", "vol_20d", "sma_ratio_20_50", "macd_hist", "ret_lag_5", "atr_14_pct", "ema_ratio_12_26", "ret_lag_1"]
TICKER = "SPY"
TRAIN_START = "2010-01-01"
TRAIN_END = "2017-12-31"
RANDOM_STATE = 0
LABEL_DESCRIPTION = "next-day close-to-close return > 0"


def model_specs():
    from sklearn.linear_model import LogisticRegression
    from sklearn.neural_network import MLPClassifier
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler
    from sklearn.tree import DecisionTreeClassifier
    from xgboost import XGBClassifier

    return [
        ("demo_decision_tree", "Decision tree", "DecisionTreeClassifier",
         DecisionTreeClassifier(max_depth=5, min_samples_leaf=50, random_state=RANDOM_STATE)),
        ("demo_logistic_regression", "Logistic regression", "LogisticRegression",
         Pipeline([("scaler", StandardScaler()), ("model", LogisticRegression(max_iter=1000, random_state=RANDOM_STATE))])),
        ("demo_mlp", "Small neural network (MLP)", "MLPClassifier",
         Pipeline([("scaler", StandardScaler()), ("model", MLPClassifier(hidden_layer_sizes=(16, 8), max_iter=500, random_state=RANDOM_STATE))])),
        ("demo_xgboost", "XGBoost", "XGBClassifier",
         XGBClassifier(n_estimators=200, max_depth=3, learning_rate=0.05, subsample=0.8, random_state=RANDOM_STATE)),
    ]


def training_data():
    import pandas as pd
    from app.data.indicators import compute_indicators

    ohlcv = pd.read_csv(Path(CONTAINER_REPO) / "app" / "data" / "fallback" / f"{TICKER}.csv", dtype={"date": str})
    features = compute_indicators(ohlcv, FEATURES)
    next_close = ohlcv["close"].shift(-1)
    label = (next_close > ohlcv["close"]).astype(int)
    mask = (
        features.notna().all(axis=1)
        & next_close.notna()
        & (ohlcv["date"] >= TRAIN_START)
        & (ohlcv["date"] <= TRAIN_END)
    )
    return features.loc[mask, FEATURES].reset_index(drop=True), label[mask].reset_index(drop=True), ohlcv.loc[mask, "date"]


def train_inside() -> None:
    import joblib

    X, y, dates = training_data()
    manifest = []
    for model_id, name, family, model in model_specs():
        model.fit(X, y)
        file_name = f"{model_id}.joblib"
        joblib.dump(model, Path(CONTAINER_OUTPUT) / file_name)
        manifest.append({
            "id": model_id,
            "name": name,
            "family": family,
            "file": file_name,
            "feature_columns": FEATURES,
            "signal_type": "discrete",
            "explained_output": "P(buy)",
            "trained_on": {
                "ticker": TICKER,
                "start": str(dates.iloc[0]),
                "end": str(dates.iloc[-1]),
                "n_rows": int(len(X)),
                "label": LABEL_DESCRIPTION,
                "random_state": RANDOM_STATE,
            },
        })
        print(f"{model_id}: trained on {len(X)} rows, in-sample accuracy {model.score(X, y):.4f}")
    with open(Path(CONTAINER_OUTPUT) / "manifest.json", "w", encoding="utf-8") as f:
        json.dump({"models": manifest}, f, indent=2)
        f.write("\n")


def run_in_container() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    command = [
        "docker", "run", "--rm",
        "--network=none",
        "-v", f"{BACKEND_DIR}:{CONTAINER_REPO}:ro",
        "-v", f"{OUTPUT_DIR}:{CONTAINER_OUTPUT}",
        "-w", CONTAINER_REPO,
        "-e", f"PYTHONPATH={CONTAINER_REPO}",
        SANDBOX_IMAGE,
        "python", f"{CONTAINER_REPO}/scripts/build_demo_models.py", INSIDE_FLAG,
    ]
    subprocess.run(command, check=True)


if __name__ == "__main__":
    if INSIDE_FLAG in sys.argv:
        train_inside()
    else:
        run_in_container()
