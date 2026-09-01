import pickle
import pandas as pd
from sklearn.tree import DecisionTreeClassifier
from app.models.wrapper import ModelMetadata, SignalType
from app.models.validation import register_model
from app.explainability.shap_engine import compute_shap_explanation
from app.tests.conftest import requires_docker


@requires_docker
def test_shap_additivity_within_epsilon():
    X_train = pd.DataFrame({
        "open": [100.0, 100.0, 50.0, 80.0, 80.0, 90.0, 95.0, 60.0],
        "close": [105.0, 95.0, 50.0, 85.0, 75.0, 92.0, 98.0, 55.0],
    })
    y_train = [1, -1, -1, 1, -1, 1, 1, -1]

    model = DecisionTreeClassifier(max_depth=2, random_state=0)
    model.fit(X_train, y_train)
    model_bytes = pickle.dumps(model)

    metadata = ModelMetadata(
        name="test_additivity_model",
        signal_type=SignalType.DISCRETE,
        expected_columns=["open", "close"],
    )
    registered = register_model(metadata, model_bytes, "test_additivity_model.pkl")

    records = X_train.to_dict(orient="records")

    explanation = compute_shap_explanation(
        model_storage_path=registered.storage_path,
        records=records,
        background_records=records,
    )

    assert explanation["additivity_error"] <= 0.01