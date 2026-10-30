import numpy as np
import pandas as pd
from app.sandbox.explain_core import explained_output_info, is_classifier, model_output
from app.sandbox.sandbox_common import SandboxTaskError, run_entrypoint

SUPPORTED_MODULE_ROOTS = ("sklearn", "xgboost", "lightgbm")


def final_estimator(model):
    steps = getattr(model, "steps", None)
    if steps:
        return final_estimator(steps[-1][1])
    return model


def check_supported(model) -> None:
    root = type(model).__module__.split(".")[0]
    if root not in SUPPORTED_MODULE_ROOTS:
        raise SandboxTaskError(
            f"Unsupported model type '{type(model).__module__}.{type(model).__name__}'. Supported libraries: scikit-learn, xgboost, lightgbm.",
            code="unsupported_model",
        )
    if not hasattr(model, "predict"):
        raise SandboxTaskError("The model has no predict method.", code="unsupported_model")
    if hasattr(model, "classes_") and not hasattr(model, "predict_proba"):
        raise SandboxTaskError("Classifiers must implement predict_proba.", code="unsupported_model")


def resolve_column_order(model, requested: list[str]) -> list[str]:
    names = getattr(model, "feature_names_in_", None)
    if names is not None:
        model_names = [str(name) for name in names]
        if set(model_names) != set(requested) or len(model_names) != len(requested):
            missing = [name for name in model_names if name not in requested]
            unexpected = [name for name in requested if name not in model_names]
            raise SandboxTaskError(
                f"Feature names do not match the model. Expected by the model but not provided: {missing}. Provided but unknown to the model: {unexpected}.",
                code="feature_mismatch",
                details={"model_features": model_names, "missing": missing, "unexpected": unexpected},
            )
        return model_names
    n_features = getattr(model, "n_features_in_", None)
    if n_features is not None and int(n_features) != len(requested):
        raise SandboxTaskError(
            f"The model expects {int(n_features)} features but {len(requested)} were provided.",
            code="feature_count_mismatch",
            details={"expected": int(n_features), "provided": len(requested)},
        )
    return list(requested)


def check_outputs(outputs: np.ndarray, n_rows: int, classifier: bool) -> None:
    if outputs.shape != (n_rows,):
        raise SandboxTaskError(f"The model returned {outputs.shape} outputs for {n_rows} rows.", code="signal_contract_violation")
    finite = outputs[np.isfinite(outputs)]
    if classifier and ((finite < 0) | (finite > 1)).any():
        raise SandboxTaskError("Class probabilities must lie in [0, 1].", code="signal_contract_violation")


def compute_outputs(model, rows: list[list[float]], columns: list[str]) -> np.ndarray:
    X = pd.DataFrame(rows, columns=columns, dtype=float)
    try:
        outputs = model_output(model, X)
    except SandboxTaskError:
        raise
    except Exception as exc:
        raise SandboxTaskError(f"The model failed to predict: {type(exc).__name__}: {exc}", code="predict_failed")
    check_outputs(outputs, len(X), is_classifier(model))
    return outputs


def handle_preflight(model, payload: dict) -> dict:
    check_supported(model)
    requested = list(payload["feature_names"])
    column_order = resolve_column_order(model, requested)
    reordered_rows = pd.DataFrame(payload["rows"], columns=requested, dtype=float)[column_order].to_numpy().tolist()
    outputs = compute_outputs(model, reordered_rows, column_order)
    info = explained_output_info(model)
    estimator = final_estimator(model)
    return {
        "column_order": column_order,
        "reordered": column_order != requested,
        "signal_type": "discrete" if info["kind"] == "classifier" else "continuous",
        "explained_output": info["explained_output"],
        "explained_class": info["explained_class"],
        "model_class": f"{type(model).__module__}.{type(model).__name__}",
        "family": type(estimator).__name__,
        "sample_outputs": outputs.tolist(),
    }


def handle_predict(model, payload: dict) -> dict:
    check_supported(model)
    outputs = compute_outputs(model, payload["rows"], list(payload["feature_names"]))
    return {"outputs": outputs.tolist()}


def handle(model, payload: dict) -> dict:
    if payload.get("mode") == "preflight":
        return handle_preflight(model, payload)
    return handle_predict(model, payload)


if __name__ == "__main__":
    run_entrypoint(handle)
