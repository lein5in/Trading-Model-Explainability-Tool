import pickle
import pandas as pd
import numpy as np
from sklearn.tree import DecisionTreeRegressor
from app.models.wrapper import ModelMetadata, SignalType
from app.models.validation import register_model
from app.explainability.shap_engine import compute_shap_explanation, compute_global_feature_importance


def build_rsi_only_model():
    np.random.seed(0)
    n = 200
    rsi = np.random.uniform(0, 100, n)
    noise_feature = np.random.uniform(0, 100, n)
    target = np.where(rsi > 50, 1.0, -1.0)

    X = pd.DataFrame({"rsi": rsi, "noise_feature": noise_feature})
    model = DecisionTreeRegressor(max_depth=3, random_state=0)
    model.fit(X, target)

    return pickle.dumps(model), X


def run_single_feature_sanity_check() -> dict:
    model_bytes, X = build_rsi_only_model()

    metadata = ModelMetadata(
        name="synthetic_rsi_only",
        signal_type=SignalType.CONTINUOUS,
        expected_columns=["rsi", "noise_feature"],
    )
    registered = register_model(metadata, model_bytes, "synthetic_rsi_only.pkl")

    sample = X.sample(n=30, random_state=0)
    records = sample.to_dict(orient="records")
    background_records = X.sample(n=50, random_state=1).to_dict(orient="records")

    explanation = compute_shap_explanation(
        model_storage_path=registered.storage_path,
        records=records,
        background_records=background_records,
    )

    importance = compute_global_feature_importance(
        explanation["shap_values"], explanation["feature_names"]
    )

    total_importance = sum(importance.values())
    rsi_share = importance["rsi"] / total_importance if total_importance > 0 else 0.0

    passed = rsi_share > 0.9

    return {
        "passed": passed,
        "rsi_share": rsi_share,
        "importance": importance,
        "additivity_error": explanation["additivity_error"],
        "explainer_type": explanation["explainer_type"],
    }


if __name__ == "__main__":
    result = run_single_feature_sanity_check()
    print(result)
    if not result["passed"]:
        raise SystemExit("Sanity check FAILED: RSI feature does not dominate SHAP attribution as expected.")
    print("Sanity check PASSED.")