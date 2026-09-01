import pickle
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

np.random.seed(0)

n_samples = 2000
open_prices = np.random.uniform(1.0, 1000.0, n_samples)
daily_return = np.random.normal(0.0, 0.02, n_samples)
close_prices = open_prices * (1.0 + daily_return)

X_train = pd.DataFrame({
    "open": open_prices,
    "close": close_prices,
})

signal = np.where(close_prices >= open_prices, -1, 1)

model = LogisticRegression()
model.fit(X_train, signal)

with open("test_model.pkl", "wb") as f:
    pickle.dump(model, f)

print("Modele cree : test_model.pkl")
print("Repartition des signaux d'entrainement :", pd.Series(signal).value_counts().to_dict())
print("Accuracy sur donnees d'entrainement :", model.score(X_train, signal))