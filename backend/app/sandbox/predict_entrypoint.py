import sys
import json
import pickle
import joblib
import pandas as pd
import numpy as np


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

        if not hasattr(model, "predict"):
            raise AttributeError("Loaded object has no 'predict' method.")

        predictions = model.predict(X)
        predictions_list = np.asarray(predictions).tolist()

        result = {"success": True, "predictions": predictions_list, "error": None}

    except Exception as exc:
        result = {"success": False, "predictions": None, "error": str(exc)}

    with open(output_path, "w") as f:
        json.dump(result, f)


if __name__ == "__main__":
    main()