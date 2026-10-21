# curl -X POST http://localhost:5001/breath -H "Content-Type: application/json" -d '{"timestamp": 1001, "volume": 0.05, "pitch": 120.0}'

from flask import Flask, request, jsonify
from collections import deque
import numpy as np
import joblib

app = Flask(__name__)

# Load trained Random Forest model
model = joblib.load('breath_model.pkl')

# Maintain rolling history buffer for live time-series feature extraction (max 5 readings)
volume_history = deque(maxlen=5)
pitch_history = deque(maxlen=5)

@app.route('/breath', methods=['POST'])
def predict_breath():
    data = request.get_json()
    
    if not data or 'volume' not in data or 'pitch' not in data:
        return jsonify({'error': 'Invalid payload. Expecting keys: volume, pitch, timestamp'}), 400

    vol = float(data['volume'])
    pitch = float(data['pitch'])
    timestamp = data.get('timestamp', None)

    # Append new sensor data to rolling buffers
    volume_history.append(vol)
    pitch_history.append(pitch)

    # Calculate real-time rolling features
    vol_mean = float(np.mean(volume_history))
    vol_std = float(np.std(volume_history)) if len(volume_history) > 1 else 0.0
    pitch_mean = float(np.mean(pitch_history))
    vol_diff = float(volume_history[-1] - volume_history[-2]) if len(volume_history) > 1 else 0.0

    # Build input feature vector in exact order expected by model
    features = np.array([[
        vol,
        pitch,
        vol_mean,
        vol_std,
        pitch_mean,
        vol_diff
    ]])

    # Inference
    prediction = int(model.predict(features)[0])
    probability = float(model.predict_proba(features)[0][1])

    return jsonify({
        'timestamp': timestamp,
        'breath_active': bool(prediction),
        'confidence': round(probability, 4)
    }), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)