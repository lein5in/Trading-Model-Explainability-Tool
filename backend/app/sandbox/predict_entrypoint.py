import json
import math
import pickle
import joblib
import pandas as pd
import numpy as np


def load_model(model_path: str):
    if model_path.endswith(".joblib"):
        return joblib.load(model_path)
    with open(model_path, "rb") as f:
        return pickle.load(f)


class SignalContractViolation(Exception):
    pass


def validate_signal_contract(predictions_list: list, signal_type: str) -> None:
    for value in predictions_list:
        if value is None:
            continue
        try:
            float_value = float(value)
        except (TypeError, ValueError):
            raise SignalContractViolation(
                f"Prediction value '{value}' is not numeric."
            )

        if math.isnan(float_value):
            continue

        if signal_type == "discrete":
            if float_value not in (-1.0, 0.0, 1.0):
                raise SignalContractViolation(
                    f"signal_type declared as 'discrete' but predict() returned "
                    f"non-discrete value {float_value}. Expected one of -1, 0, 1."
                )
        elif signal_type == "continuous":
            if float_value < -1.0 or float_value > 1.0:
                raise SignalContractViolation(
                    f"signal_type declared as 'continuous' but predict() returned "
                    f"value {float_value} outside the expected range [-1, 1]."
                )
        else:
            raise SignalContractViolation(
                f"Unknown signal_type '{signal_type}'. Expected 'discrete' or 'continuous'."
            )


def main():
    model_path = "/sandbox_input/model.pkl"
    input_path = "/sandbox_input/input.json"
    output_path = "/sandbox_output/output.json"

    try:
        with open(input_path, "r") as f:
            payload = json.load(f)

        X = pd.DataFrame(payload["records"])
        signal_type = payload["signal_type"]
        model = load_model(model_path)

        if not hasattr(model, "predict"):
            raise AttributeError("Loaded object has no 'predict' method.")

        predictions = model.predict(X)
        predictions_list = np.asarray(predictions).tolist()

        validate_signal_contract(predictions_list, signal_type)

        result = {"success": True, "predictions": predictions_list, "error": None}

    except Exception as exc:
        result = {"success": False, "predictions": None, "error": str(exc)}

    with open(output_path, "w") as f:
        json.dump(result, f)


if __name__ == "__main__":
    main()