import pandas as pd
import requests

# Pointing directly to port 5001 and route /breath
SERVER_URL = "http://127.0.0.1:5001/breath"

input_file = "totest.csv"
output_file = "totest_result.csv"

df = pd.read_csv(input_file)
results = []

print(f"Sending {len(df)} requests to {SERVER_URL}...")

for index, row in df.iterrows():
    payload = {
        "timestamp": int(row["Timestamp_ms"]),
        "volume": float(row["Volume_RMS"]),
        "pitch": float(row["Pitch_Hz"]),
    }

    try:
        response = requests.post(SERVER_URL, json=payload)
        if response.status_code == 200:
            data = response.json()
            # Extract breath_active prediction (1 or 0)
            prediction = 1 if data.get("breath_active") else 0
            results.append(prediction)
        else:
            print(f"Row {index}: Server error {response.status_code}")
            results.append(None)
    except Exception as e:
        print(f"Row {index}: Connection failed - {e}")
        results.append(None)

# Append prediction column matching the original training datasets
df["Breath_Active"] = results
df.to_csv(output_file, index=False)

print(
    f"Successfully processed {len(df)} rows! Results saved to '{output_file}'."
)