from flask import Flask, request, jsonify
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import LabelEncoder
import pandas as pd
import os
import joblib
from datetime import datetime
import numpy as np
import socket
import time
from math import pi

app = Flask(__name__)

MODEL_PATH = '/data/anomaly_detection_model.pkl'
IP_ENCODER_PATH = '/data/ip_encoder.pkl'
USER_ENCODER_PATH = '/data/user_encoder.pkl'
KNOWN_IPS_FILE = '/data/known_ips.txt'

# ----------------- Utility Functions -----------------

def safe_parse_timestamp(timestamp_str):
    try:
        return pd.to_datetime(timestamp_str)
    except:
        for fmt in ['%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M', '%m/%d/%Y %H:%M:%S']:
            try:
                return datetime.strptime(timestamp_str, fmt)
            except:
                continue
        raise ValueError(f"Could not parse timestamp: {timestamp_str}")

def load_model_and_encoders():
    try:
        model = joblib.load(MODEL_PATH) if os.path.exists(MODEL_PATH) else None
        ip_encoder = joblib.load(IP_ENCODER_PATH) if os.path.exists(IP_ENCODER_PATH) else LabelEncoder()
        user_encoder = joblib.load(USER_ENCODER_PATH) if os.path.exists(USER_ENCODER_PATH) else LabelEncoder()
        return model, ip_encoder, user_encoder
    except Exception as e:
        app.logger.error(f"Error loading model/encoders: {str(e)}")
        return None, LabelEncoder(), LabelEncoder()

def save_model_and_encoders(model, ip_encoder, user_encoder):
    try:
        joblib.dump(model, MODEL_PATH)
        joblib.dump(ip_encoder, IP_ENCODER_PATH)
        joblib.dump(user_encoder, USER_ENCODER_PATH)
    except Exception as e:
        app.logger.error(f"Error saving model/encoders: {str(e)}")
        raise

def load_known_ips():
    try:
        if os.path.exists(KNOWN_IPS_FILE):
            with open(KNOWN_IPS_FILE, 'r') as f:
                return set(line.strip() for line in f if line.strip())
        return set()
    except Exception as e:
        app.logger.error(f"Error loading known IPs: {str(e)}")
        return set()

def save_known_ips(ips):
    try:
        with open(KNOWN_IPS_FILE, 'w') as f:
            for ip in sorted(ips):
                f.write(ip + '\n')
    except Exception as e:
        app.logger.error(f"Error saving known IPs: {str(e)}")
        raise

def preprocess_logs(logs, ip_encoder, user_encoder, fit_encoders=False):
    try:
        logs['timestamp'] = logs['timestamp'].apply(safe_parse_timestamp)
    except Exception as e:
        raise ValueError(f"Timestamp parsing failed: {str(e)}")

    logs['hour'] = logs['timestamp'].dt.hour
    logs['minute'] = logs['timestamp'].dt.minute
    logs['day_of_week'] = logs['timestamp'].dt.dayofweek

    logs['hour_sin'] = np.sin(2*pi*logs['hour']/24)
    logs['hour_cos'] = np.cos(2*pi*logs['hour']/24)
    logs['is_night'] = logs['hour'].apply(lambda x: 1 if x < 6 or x > 22 else 0)

    logs['result'] = logs['result'].apply(lambda x: 1 if str(x).lower() in ['success', '1', 'true'] else 0)

    if fit_encoders:
        ip_encoder.fit(logs['ip_address'])
        user_encoder.fit(logs['user_id'])

    try:
        logs['ip_encoded'] = ip_encoder.transform(logs['ip_address'])
    except ValueError:
        if fit_encoders:
            raise
        logs['ip_encoded'] = len(ip_encoder.classes_)

    try:
        logs['user_encoded'] = user_encoder.transform(logs['user_id'])
    except ValueError:
        if fit_encoders:
            raise
        logs['user_encoded'] = len(user_encoder.classes_)

    return logs[['ip_encoded', 'user_encoded', 'result', 'hour_sin', 'hour_cos', 'is_night', 'day_of_week']]

def train_model(features):
    model = IsolationForest(n_estimators=500, contamination=0.2, max_features=0.7,
                            random_state=42, verbose=1, n_jobs=-1)
    model.fit(features)
    return model

def generate_synthetic_anomalies(features, ip_encoder, user_encoder):
    synthetic_raw = []
    fake_ips = [f"10.0.0.{i}" for i in range(1, 6)]
    for ip in fake_ips:
        if ip not in ip_encoder.classes_:
            ip_encoder.classes_ = np.append(ip_encoder.classes_, ip)
    fake_users = [f"attacker_{i}" for i in range(1, 4)]
    for user in fake_users:
        if user not in user_encoder.classes_:
            user_encoder.classes_ = np.append(user_encoder.classes_, user)
    num_anomalies = max(5, len(features) // 20)
    for _ in range(num_anomalies):
        timestamp = datetime.utcnow().replace(hour=np.random.randint(0, 24), minute=np.random.randint(0, 60))
        synthetic_raw.append({
            'timestamp': timestamp.isoformat(),
            'user_id': np.random.choice(fake_users),
            'ip_address': np.random.choice(fake_ips),
            'result': 'failure'
        })
    df_raw = pd.DataFrame(synthetic_raw)
    return preprocess_logs(df_raw, ip_encoder, user_encoder, fit_encoders=False)

def get_anomaly_reason(row, score, threshold, ip_encoder, user_encoder):
    reasons = []
    if row['hour_sin'] < -0.95 or row['hour_cos'] < -0.95:
        reasons.append("unusual_time")
    if row['result'] == 0:
        reasons.append("login_failure")
    if score < threshold - 0.2:
        reasons.append("high_anomaly_score")
    if 'ip_encoded' in row and row['ip_encoded'] >= len(ip_encoder.classes_):
        reasons.append("unknown_ip")
    if 'user_encoded' in row and row['user_encoded'] >= len(user_encoder.classes_):
        reasons.append("unknown_user")
    return reasons if reasons else "unknown_reason"

@app.route('/healthz')
def health():
    try:
        return jsonify({"status": "OK", "timestamp": datetime.utcnow().isoformat()}), 200
    except Exception as e:
        return jsonify({"status": "ERROR", "error": str(e)}), 500

@app.route('/train', methods=['POST'])
def train():
    try:
        data = request.json
        logs = pd.DataFrame(data)
        required_columns = ['timestamp', 'user_id', 'ip_address', 'result']
        if not all(col in logs.columns for col in required_columns):
            return jsonify({"error": f"Missing required columns: {required_columns}"}), 400

        known_ips = load_known_ips()
        model, ip_encoder, user_encoder = load_model_and_encoders()

        new_ips = set(logs['ip_address'].astype(str).unique())
        known_ips.update(new_ips)
        save_known_ips(known_ips)

        features = preprocess_logs(logs, ip_encoder, user_encoder, fit_encoders=True)

        failure_count = len(logs[logs['result'] == 0])
        if failure_count < 3:
            synthetic = generate_synthetic_anomalies(features, ip_encoder, user_encoder)
            features = pd.concat([features, synthetic])

        model = train_model(features)
        save_model_and_encoders(model, ip_encoder, user_encoder)

        return jsonify({
            "message": "Model trained successfully",
            "stats": {
                "samples": len(logs),
                "features": features.shape[1],
                "ips": len(known_ips),
                "users": len(user_encoder.classes_),
                "failures": failure_count,
                "synthetic_added": len(features) - len(logs) if failure_count < 3 else 0
            }
        })
    except Exception as e:
        return jsonify({"error": f"Training failed: {str(e)}"}), 500

@app.route('/detect', methods=['POST'])
def detect_anomalies():
    try:
        data = request.json
        if not data:
            return jsonify({"error": "No data provided"}), 400

        logs = pd.DataFrame(data)
        required_columns = ['timestamp', 'user_id', 'ip_address', 'result']
        if not all(col in logs.columns for col in required_columns):
            return jsonify({"error": f"Missing required columns. Needed: {required_columns}"}), 400

        model, ip_encoder, user_encoder = load_model_and_encoders()
        if model is None:
            return jsonify({"error": "Model not trained yet!"}), 400

        known_ips = load_known_ips()
        try:
            features = preprocess_logs(logs, ip_encoder, user_encoder, fit_encoders=False)
        except ValueError as e:
            return jsonify({"error": f"Preprocessing error: {str(e)}"}), 400

        anomaly_scores = model.decision_function(features)
        threshold = np.percentile(anomaly_scores, 5)
        is_anomaly = anomaly_scores < threshold

        for i, row in logs.iterrows():
            ip_unknown = row['ip_address'] not in known_ips
            is_night = features.iloc[i]['is_night'] == 1
            if ip_unknown or is_night:
                is_anomaly[i] = True

        results = []
        for i, row in logs.iterrows():
            result = {
                "timestamp": str(row["timestamp"]),
                "user_id": row["user_id"],
                "ip_address": row["ip_address"],
                "result": "success" if row["result"] == 1 else "failure",
                "is_anomaly": bool(is_anomaly[i]),
                "anomaly_score": float(anomaly_scores[i]),
                "unknown_ip": row["ip_address"] not in known_ips,
                "reason": get_anomaly_reason(features.iloc[i], anomaly_scores[i], threshold, ip_encoder, user_encoder) if is_anomaly[i] else None
            }
            results.append(result)

        return jsonify({
            "results": results,
            "stats": {
                "total_logs": len(logs),
                "anomalies_detected": int(sum(is_anomaly)),
                "unknown_ips": sum(row["ip_address"] not in known_ips for _, row in logs.iterrows()),
                "anomaly_threshold": float(threshold)
            }
        })

    except Exception as e:
        return jsonify({"error": f"Detection failed: {str(e)}"}), 500

if __name__ == '__main__':
    print("Starting Flask application...")
    print(f"Host: 0.0.0.0, Port: 5000")
    os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
    print(f"Data directory ready: {os.path.dirname(MODEL_PATH)}")
    try:
        app.run(host='0.0.0.0', port=5000, threaded=True)
    except Exception as e:
        print(f"Failed to start application: {str(e)}")
        raise
