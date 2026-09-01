import pickle
import pandas as pd
from sklearn.tree import DecisionTreeClassifier
from app.models.wrapper import ModelMetadata, SignalType
from app.models.validation import register_model
from app.sandbox.runner import _run_sandbox


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
    registered = register_model(metadata, model_bytes, "diag_model.pkl")

    records = X_train.to_dict(orient="records")

    result = _run_sandbox(
        entrypoint_script="diagnose_shap_entrypoint.py",
        model_storage_path=registered.storage_path,
        payload={"records": records},
        timeout_seconds=60,
    )

    print(result)


if __name__ == "__main__":
    main()