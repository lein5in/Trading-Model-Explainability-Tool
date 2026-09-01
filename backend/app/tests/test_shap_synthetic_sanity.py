from app.explainability.tests_synthetic import run_single_feature_sanity_check
from app.tests.conftest import requires_docker


@requires_docker
def test_rsi_feature_dominates_shap_attribution():
    result = run_single_feature_sanity_check()

    assert result["rsi_share"] > 0.9
    assert result["additivity_error"] <= 0.01