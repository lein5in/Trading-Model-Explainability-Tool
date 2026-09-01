import json
import pickle
import joblib
import pandas as pd
import numpy as np
import shap


def load_model(model_path: str):
    if model_path.endswith(".joblib"):
        return joblib.load(model_path)
    with open(model_path, "rb") as f:
        return pickle.load(f)


TREE_MODEL_MODULES = {
    "sklearn.tree",
    "sklearn.ensemble",
    "xgboost.sklearn",
    "xgboost.core",
    "lightgbm.sklearn",
    "lightgbm.basic",
}


def is_tree_model(model) -> bool:
    module_name = type(model).__module__
    return any(module_name.startswith(prefix) for prefix in TREE_MODEL_MODULES)


def build_explainer(model, background_data: pd.DataFrame):
    if is_tree_model(model):
        return shap.TreeExplainer(model), "tree"
    summarized_background = shap.kmeans(background_data, min(50, len(background_data)))
    if hasattr(model, "predict_proba"):
        def predict_positive_class_proba(X):
            return np.asarray(model.predict_proba(X))[:, -1]
        return shap.KernelExplainer(predict_positive_class_proba, summarized_background), "kernel"
    return shap.KernelExplainer(model.predict, summarized_background), "kernel"


def normalize_shap_output(raw_shap_values, raw_expected_value):
    if isinstance(raw_shap_values, list):
        shap_values = np.asarray(raw_shap_values[-1])
        base_value = raw_expected_value[-1] if isinstance(raw_expected_value, (list, np.ndarray)) else raw_expected_value
        return shap_values, float(base_value)

    array = np.asarray(raw_shap_values)

    if array.ndim == 3:
        shap_values = array[:, :, -1]
        base_value = raw_expected_value[-1] if isinstance(raw_expected_value, (list, np.ndarray)) else raw_expected_value
        return shap_values, float(base_value)

    base_value = raw_expected_value
    if isinstance(base_value, (list, np.ndarray)):
        base_value = np.asarray(base_value).flatten()[-1]
    return array, float(base_value)


def get_additivity_target(model, X: pd.DataFrame) -> np.ndarray:
    if hasattr(model, "predict_proba"):
        proba = np.asarray(model.predict_proba(X))
        return proba[:, -1].astype(float)
    return np.asarray(model.predict(X)).flatten().astype(float)


def main():
    model_path = "/sandbox_input/model.pkl"
    input_path = "/sandbox_input/input.json"
    output_path = "/sandbox_output/output.json"

    try:
        with open(input_path, "r") as f:
            payload = json.load(f)

        X = pd.DataFrame(payload["records"])
        background_records = payload.get("background_records", payload["records"])
        background_X = pd.DataFrame(background_records)

        model = load_model(model_path)

        if not hasattr(model, "predict"):
            raise AttributeError("Loaded object has no 'predict' method.")

        explainer, explainer_type = build_explainer(model, background_X)
        raw_shap_values = explainer.shap_values(X)

        shap_values, base_value = normalize_shap_output(raw_shap_values, explainer.expected_value)

        additivity_target = get_additivity_target(model, X)
        reconstructed = shap_values.sum(axis=1) + base_value
        additivity_error = float(np.max(np.abs(reconstructed - additivity_target)))

        result = {
            "success": True,
            "error": None,
            "explainer_type": explainer_type,
            "shap_values": shap_values.tolist(),
            "base_value": base_value,
            "feature_names": list(X.columns),
            "additivity_error": additivity_error,
        }

    except Exception as exc:
        result = {"success": False, "error": str(exc)}

    with open(output_path, "w") as f:
        json.dump(result, f)


if __name__ == "__main__":
    main()