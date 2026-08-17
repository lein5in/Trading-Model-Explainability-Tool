from app.sandbox.runner import run_explain_in_sandbox

ADDITIVITY_EPSILON = 0.01


class AdditivityCheckFailed(Exception):
    pass


def compute_shap_explanation(
    model_storage_path: str,
    records: list[dict],
    background_records: list[dict] = None,
) -> dict:
    result = run_explain_in_sandbox(
        model_storage_path=model_storage_path,
        records=records,
        background_records=background_records,
    )

    if result["additivity_error"] > ADDITIVITY_EPSILON:
        raise AdditivityCheckFailed(
            f"SHAP additivity check failed: error={result['additivity_error']} "
            f"exceeds epsilon={ADDITIVITY_EPSILON}"
        )

    return result


def compute_global_feature_importance(shap_values: list, feature_names: list[str]) -> dict:
    import numpy as np

    values_array = np.abs(np.asarray(shap_values))
    mean_abs_shap = values_array.mean(axis=0)

    return {
        name: float(score)
        for name, score in zip(feature_names, mean_abs_shap)
    }