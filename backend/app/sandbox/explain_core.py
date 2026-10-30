import numpy as np
import pandas as pd

DEFAULT_ADDITIVITY_EPSILON = 0.01
DEFAULT_KERNEL_NSAMPLES = 200
DEFAULT_KERNEL_BACKGROUND_SIZE = 10
TREE_BACKGROUND_SIZE = 100
EXPLAINED_PROBABILITY_LABEL = "P(buy)"
EXPLAINED_PREDICTION_LABEL = "prediction"
TREE_MODEL_MODULE_PREFIXES = (
    "sklearn.tree",
    "sklearn.ensemble",
    "xgboost",
    "lightgbm",
)


class AdditivityError(Exception):
    def __init__(self, max_gap: float, epsilon: float):
        super().__init__(f"SHAP additivity check failed: max gap {max_gap:.6g} exceeds {epsilon:g}.")
        self.max_gap = max_gap
        self.epsilon = epsilon


def is_classifier(model) -> bool:
    return hasattr(model, "classes_") and hasattr(model, "predict_proba")


def positive_class_index(model) -> int:
    classes = list(model.classes_)
    for index, label in enumerate(classes):
        if not isinstance(label, (bool, np.bool_, str)) and label == 1:
            return index
    return classes.index(max(classes))


def label_to_json(label):
    if isinstance(label, (np.integer,)):
        return int(label)
    if isinstance(label, (np.floating,)):
        return float(label)
    if isinstance(label, (np.bool_,)):
        return bool(label)
    return label


def explained_output_info(model) -> dict:
    if is_classifier(model):
        index = positive_class_index(model)
        return {
            "kind": "classifier",
            "explained_output": EXPLAINED_PROBABILITY_LABEL,
            "explained_class": label_to_json(list(model.classes_)[index]),
            "positive_index": index,
        }
    return {"kind": "regressor", "explained_output": EXPLAINED_PREDICTION_LABEL, "explained_class": None, "positive_index": None}


def model_output(model, X: pd.DataFrame) -> np.ndarray:
    if is_classifier(model):
        return np.asarray(model.predict_proba(X), dtype=float)[:, positive_class_index(model)]
    return np.asarray(model.predict(X), dtype=float).reshape(len(X), -1)[:, 0]


def is_tree_model(model) -> bool:
    module_name = type(model).__module__
    return any(module_name.startswith(prefix) for prefix in TREE_MODEL_MODULE_PREFIXES)


def select_output(raw_values, expected_value, positive_index: int | None) -> tuple[np.ndarray, float]:
    expected = np.atleast_1d(np.asarray(expected_value, dtype=float))
    if isinstance(raw_values, list):
        index = positive_index if positive_index is not None else len(raw_values) - 1
        return np.asarray(raw_values[index], dtype=float), float(expected[index])
    values = np.asarray(raw_values, dtype=float)
    if values.ndim == 3:
        index = positive_index if positive_index is not None else values.shape[2] - 1
        return values[:, :, index], float(expected[index] if len(expected) > 1 else expected[0])
    if len(expected) > 1:
        index = positive_index if positive_index is not None else len(expected) - 1
        return values, float(expected[index])
    return values, float(expected[0])


def sample_background(background: pd.DataFrame, size: int) -> pd.DataFrame:
    if len(background) <= size:
        return background
    return background.sample(n=size, random_state=0)


def tree_shap(model, X: pd.DataFrame, background: pd.DataFrame, info: dict) -> tuple[np.ndarray, float]:
    import shap

    explainer = shap.TreeExplainer(
        model,
        data=sample_background(background, TREE_BACKGROUND_SIZE),
        feature_perturbation="interventional",
        model_output="probability" if info["kind"] == "classifier" else "raw",
    )
    raw = explainer.shap_values(X, check_additivity=False)
    return select_output(raw, explainer.expected_value, info["positive_index"] if info["kind"] == "classifier" else None)


def kernel_shap(model, X: pd.DataFrame, background: pd.DataFrame, nsamples: int, background_size: int) -> tuple[np.ndarray, float]:
    import shap

    columns = list(X.columns)
    summary = shap.kmeans(background.to_numpy(dtype=float), min(background_size, len(background)))

    def predict(array):
        return model_output(model, pd.DataFrame(np.asarray(array, dtype=float), columns=columns))

    explainer = shap.KernelExplainer(predict, summary)
    raw = explainer.shap_values(X.to_numpy(dtype=float), nsamples=nsamples, silent=True, l1_reg=False)
    return select_output(raw, explainer.expected_value, None)


def additivity_gap(values: np.ndarray, base_value: float, outputs: np.ndarray) -> float:
    if len(outputs) == 0:
        return 0.0
    return float(np.max(np.abs(values.sum(axis=1) + base_value - outputs)))


def explain(
    model,
    X: pd.DataFrame,
    background: pd.DataFrame,
    epsilon: float = DEFAULT_ADDITIVITY_EPSILON,
    nsamples: int = DEFAULT_KERNEL_NSAMPLES,
    kernel_background_size: int = DEFAULT_KERNEL_BACKGROUND_SIZE,
) -> dict:
    info = explained_output_info(model)
    explainer = "kernel"
    values = None
    if is_tree_model(model):
        try:
            values, base_value = tree_shap(model, X, background, info)
            explainer = "tree"
        except Exception:
            values = None
    if values is None:
        values, base_value = kernel_shap(model, X, background, nsamples, kernel_background_size)

    outputs = model_output(model, X)
    gap = additivity_gap(values, base_value, outputs)
    if not np.isfinite(gap) or gap > epsilon:
        raise AdditivityError(gap, epsilon)

    return {
        "explainer": explainer,
        "explained_output": info["explained_output"],
        "explained_class": info["explained_class"],
        "values": values,
        "base_value": base_value,
        "outputs": outputs,
        "max_additivity_gap": gap,
    }
