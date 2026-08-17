import json
import pickle
import joblib
import pandas as pd
import numpy as np
import shap
import traceback


def load_model(model_path: str):
    if model_path.endswith(".joblib"):
        return joblib.load(model_path)
    with open(model_path, "rb") as f:
        return pickle.load(f)


def main():
    model_path = "/sandbox_input/model.pkl"
    input_path = "/sandbox_input/input.json"
    output_path = "/sandbox_output/output.json"

    try:
        with open(input_path, "r") as f:
            payload = json.load(f)

        X = pd.DataFrame(payload["records"])
        model = load_model(model_path)

        explainer = shap.TreeExplainer(model)
        raw_shap_values = explainer.shap_values(X)

        debug_info = {
            "success": True,
            "type_of_raw": str(type(raw_shap_values)),
            "is_list": isinstance(raw_shap_values, list),
        }

        if isinstance(raw_shap_values, list):
            debug_info["list_length"] = len(raw_shap_values)
            debug_info["shapes_in_list"] = [list(np.asarray(v).shape) for v in raw_shap_values]
        else:
            debug_info["shape"] = list(np.asarray(raw_shap_values).shape)

        debug_info["expected_value_type"] = str(type(explainer.expected_value))
        debug_info["expected_value"] = (
            np.asarray(explainer.expected_value).tolist()
            if hasattr(explainer.expected_value, "__len__")
            else float(explainer.expected_value)
        )

        debug_info["predict_output_sample"] = np.asarray(model.predict(X)).flatten()[:5].tolist()
        if hasattr(model, "predict_proba"):
            proba = np.asarray(model.predict_proba(X))
            debug_info["predict_proba_shape"] = list(proba.shape)
            debug_info["predict_proba_sample"] = proba[:5].tolist()

            if not isinstance(raw_shap_values, list):
                arr = np.asarray(raw_shap_values)
                if arr.ndim == 3:
                    shap_slice = arr[:, :, -1]
                    reconstructed_vs_proba = shap_slice.sum(axis=1) + explainer.expected_value[-1]
                    debug_info["reconstructed_vs_proba_positive_class"] = reconstructed_vs_proba[:5].tolist()
                    debug_info["actual_proba_positive_class"] = proba[:5, -1].tolist()

    except Exception:
        debug_info = {"success": False, "traceback": traceback.format_exc()}

    with open(output_path, "w") as f:
        json.dump(debug_info, f, indent=2)


if __name__ == "__main__":
    main()