from app.sandbox.runner import run_explain_in_sandbox, run_predict_in_sandbox, run_preflight_in_sandbox


class SandboxClient:
    def preflight(self, model_path: str, feature_names: list[str], rows: list[list[float]], timeout_seconds: float) -> dict:
        return run_preflight_in_sandbox(model_path, feature_names, rows, timeout_seconds)

    def predict(self, model_path: str, feature_names: list[str], rows: list[list[float]], timeout_seconds: float) -> dict:
        return run_predict_in_sandbox(model_path, feature_names, rows, timeout_seconds)

    def explain(self, model_path: str, payload: dict, timeout_seconds: float) -> dict:
        return run_explain_in_sandbox(model_path, payload, timeout_seconds)
