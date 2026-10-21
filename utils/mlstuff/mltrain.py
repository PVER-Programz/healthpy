import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, accuracy_score
import joblib

# 1. Load CSV datasets
files = ['breath_data_doddi.csv', 'breath_data_pavan.csv', 'breath_data_pramod.csv']
dfs = []

for file in files:
    df = pd.read_csv(file)
    
    # Time-series feature engineering per individual dataset
    df['Volume_RMS_rolling_mean'] = df['Volume_RMS'].rolling(window=5, min_periods=1).mean()
    df['Volume_RMS_rolling_std'] = df['Volume_RMS'].rolling(window=5, min_periods=1).std().fillna(0)
    df['Pitch_Hz_rolling_mean'] = df['Pitch_Hz'].rolling(window=5, min_periods=1).mean()
    df['Volume_RMS_diff'] = df['Volume_RMS'].diff().fillna(0)
    
    dfs.append(df)

data = pd.concat(dfs, ignore_index=True)

# 2. Features and Target
features = [
    'Volume_RMS', 
    'Pitch_Hz', 
    'Volume_RMS_rolling_mean', 
    'Volume_RMS_rolling_std', 
    'Pitch_Hz_rolling_mean', 
    'Volume_RMS_diff'
]
target = 'Breath_Active'

X = data[features]
y = data[target]

# 3. Train-Test Split
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.20, random_state=42, stratify=y
)

# 4. Fit Random Forest Model
model = RandomForestClassifier(n_estimators=100, random_state=42)
model.fit(X_train, y_train)

# 5. Evaluate Model
y_pred = model.predict(X_test)
print(f"Model Accuracy: {accuracy_score(y_test, y_pred) * 100:.2f}%\n")
print(classification_report(y_test, y_pred, target_names=['Inactive', 'Active']))

# 6. Save model binary
joblib.dump(model, 'breath_model.pkl')
print("Model saved as 'breath_model.pkl'")