import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split, cross_val_predict, KFold
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import OneHotEncoder
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.metrics import mean_absolute_error, r2_score
import joblib
import os


def train():
    data = pd.read_csv('data/agrismart_crops.csv')

    # input features
    X = data[['crop_type', 'season', 'region']]

    # predict price and demand level
    y = data[['target_price', 'demand_label']].copy()
    y['demand_label'] = y['demand_label'].map({'High': 2, 'Medium': 1, 'Low': 0})

    # encode categorical columns
    preprocessor = ColumnTransformer(
        transformers=[('cat', OneHotEncoder(handle_unknown='ignore'), ['crop_type', 'season', 'region'])],
        remainder='passthrough'
    )

    # pipeline: preprocessing + model
    model = Pipeline(steps=[
        ('preprocessor', preprocessor),
        ('regressor', RandomForestRegressor(n_estimators=100, random_state=42))
    ])

    # train test split
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    model.fit(X_train, y_train)
    y_pred = model.predict(X_test)
    yt = y_test.values

    # check accuracy
    price_mae = mean_absolute_error(yt[:, 0], y_pred[:, 0])
    price_r2 = r2_score(yt[:, 0], y_pred[:, 0])
    demand_mae = mean_absolute_error(yt[:, 1], y_pred[:, 1])
    demand_r2 = r2_score(yt[:, 1], y_pred[:, 1])

    print("model trained.")
    print("Test rows:", len(X_test))
    print("PRICE  - MAE:", round(price_mae, 2), "| R2:", round(price_r2, 3))
    print("DEMAND - MAE:", round(demand_mae, 2), "| R2:", round(demand_r2, 3))

    # cross validation
    cv_pred = cross_val_predict(model, X, y, cv=KFold(5, shuffle=True, random_state=42))
    cv_y = y.values
    print("5-fold CV PRICE  R2:", round(r2_score(cv_y[:, 0], cv_pred[:, 0]), 3))
    print("5-fold CV DEMAND R2:", round(r2_score(cv_y[:, 1], cv_pred[:, 1]), 3))
    print("Note: demand labels in this dataset are random, so a negative demand R2 is expected.")

    # save model
    os.makedirs('models', exist_ok=True)
    joblib.dump(model, 'models/model.pkl')
    print("model.pkl saved in models folder")


if __name__ == "__main__":
    train()