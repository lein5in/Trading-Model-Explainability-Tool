import numpy as np
import pandas as pd
from hmmlearn.hmm import GaussianHMM
from app.regime.hmm_detector import compute_features
from scripts.diagnostics.test_sandbox_e2e import build_synthetic_ohlcv


def main():
    ohlcv = build_synthetic_ohlcv(n=300)
    features = compute_features(ohlcv)
    clean_features = features.dropna()

    raw_values = clean_features.values
    means = raw_values.mean(axis=0)
    stds = raw_values.std(axis=0)
    standardized = (raw_values - means) / stds

    print("Standardized feature stats:")
    print(pd.DataFrame(standardized, columns=clean_features.columns).describe())
    print()

    model = GaussianHMM(
        n_components=3,
        covariance_type="diag",
        n_iter=500,
        random_state=42,
    )
    model.fit(standardized)

    print("Means per state (standardized returns, volatility):")
    print(model.means_)
    print()

    print("Covariances per state (diag):")
    print(model.covars_)
    print()

    print("Transition matrix:")
    print(model.transmat_)
    print()

    predicted_states = model.predict(standardized)
    unique, counts = np.unique(predicted_states, return_counts=True)
    print("Predicted state distribution:", dict(zip(unique.tolist(), counts.tolist())))
    print()

    filtered_proba = model.predict_proba(standardized)
    n = len(filtered_proba)
    print("Filtered proba at bar 30 (early, trend-up phase):", filtered_proba[30])
    print("Filtered proba at bar 130 (trend-down phase):", filtered_proba[130])
    print("Filtered proba at bar 250 (choppy phase):", filtered_proba[250])
    print()

    argmax_states = filtered_proba.argmax(axis=1)
    unique2, counts2 = np.unique(argmax_states, return_counts=True)
    print("Argmax of filtered proba distribution:", dict(zip(unique2.tolist(), counts2.tolist())))


if __name__ == "__main__":
    main()