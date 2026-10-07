import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import OneHotEncoder
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.metrics import mean_absolute_error, r2_score
import joblib
import os

def train():
    data = pd.read_csv('data/agrismart_crops.csv')
    X = data[['crop_type', 'season', 'region']]
    y = data[['target_price', 'demand_label']].copy()
    y['demand_label'] = y['demand_label'].map({'High': 2, 'Medium': 1, 'Low': 0})
    preprocessor = ColumnTransformer(
        transformers=[('cat', OneHotEncoder(handle_unknown='ignore'), ['crop_type', 'season', 'region'])],
        remainder='passthrough'
    )
    model = Pipeline(steps=[
        ('preprocessor', preprocessor),
        ('regressor', RandomForestRegressor(n_estimators=100, random_state=42))
    ])
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    model.fit(X_train, y_train)
    y_pred = model.predict(X_test)
    
    # Evaluation metrics
    mae = mean_absolute_error(y_test, y_pred)
    r2 = r2_score(y_test, y_pred, multioutput='uniform_average')
    
    print("model trained. MAE:", round(mae, 2))
    print("R² score:", round(r2, 4))
    print("accuracy approx:", round(max(0, 100 - (mae / 100) * 100), 2), "%")
    
    os.makedirs('models', exist_ok=True)
    joblib.dump(model, 'models/model.pkl')
    print("model.pkl saved in models folder")

if __name__ == "__main__":
    train()