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

app = Flask(__name__)

MODEL_PATH = '/data/anomaly_detection_model.pkl'
IP_ENCODER_PATH = '/data/ip_encoder.pkl'
USER_ENCODER_PATH = '/data/user_encoder.pkl'
KNOWN_IPS_FILE = '/data/known_ips.txt'

# ----------------- Utility Functions -----------------

def load_model_and_encoders():
    """Load or initialize model and encoders"""
    try:
        model = joblib.load(MODEL_PATH) if os.path.exists(MODEL_PATH) else None
        ip_encoder = joblib.load(IP_ENCODER_PATH) if os.path.exists(IP_ENCODER_PATH) else LabelEncoder()
        user_encoder = joblib.load(USER_ENCODER_PATH) if os.path.exists(USER_ENCODER_PATH) else LabelEncoder()
        return model, ip_encoder, user_encoder
    except Exception as e:
        app.logger.error(f"Error loading model/encoders: {str(e)}")
        return None, LabelEncoder(), LabelEncoder()

def save_model_and_encoders(model, ip_encoder, user_encoder):
    """Save model and encoders to disk"""
    try:
        joblib.dump(model, MODEL_PATH)
        joblib.dump(ip_encoder, IP_ENCODER_PATH)
        joblib.dump(user_encoder, USER_ENCODER_PATH)
    except Exception as e:
        app.logger.error(f"Error saving model/encoders: {str(e)}")
        raise

def load_known_ips():
    """Load known IP addresses from file"""
    try:
        if os.path.exists(KNOWN_IPS_FILE):
            with open(KNOWN_IPS_FILE, 'r') as f:
                return set(line.strip() for line in f if line.strip())
        return set()
    except Exception as e:
        app.logger.error(f"Error loading known IPs: {str(e)}")
        return set()

def save_known_ips(ips):
    """Save known IP addresses to file"""
    try:
        with open(KNOWN_IPS_FILE, 'w') as f:
            for ip in sorted(ips):
                f.write(ip + '\n')
    except Exception as e:
        app.logger.error(f"Error saving known IPs: {str(e)}")
        raise

def preprocess_logs(logs, ip_encoder, user_encoder, fit_encoders=False):
    """Preprocess log data for model training/detection"""
    # Convert timestamp to numerical features
    logs['timestamp'] = pd.to_datetime(logs['timestamp'])
    logs['hour'] = logs['timestamp'].dt.hour
    logs['minute'] = logs['timestamp'].dt.minute
    logs['day_of_week'] = logs['timestamp'].dt.dayofweek
    
    # Encode result
    logs['result'] = logs['result'].apply(lambda x: 1 if str(x).lower() == 'success' else 0)
    
    # Handle new IPs and users during inference
    if fit_encoders:
        ip_encoder.fit(logs['ip_address'])
        user_encoder.fit(logs['user_id'])
    
    # Transform IPs and users
    try:
        logs['ip_encoded'] = ip_encoder.transform(logs['ip_address'])
    except ValueError:
        if fit_encoders:
            raise
        # During inference, assign a special value for unseen IPs
        logs['ip_encoded'] = len(ip_encoder.classes_)
    
    try:
        logs['user_encoded'] = user_encoder.transform(logs['user_id'])
    except ValueError:
        if fit_encoders:
            raise
        # During inference, assign a special value for unseen users
        logs['user_encoded'] = len(user_encoder.classes_)
    
    return logs[['ip_encoded', 'user_encoded', 'result', 'hour', 'minute', 'day_of_week']]

def train_model(features):
    """Train isolation forest model"""
    model = IsolationForest(
        n_estimators=200,
        contamination=0.1,
        max_features=1.0,
        bootstrap=False,
        random_state=42,
        verbose=1,
        n_jobs=-1
    )
    model.fit(features)
    return model

def generate_synthetic_anomalies(features, ip_encoder, user_encoder):
    """Generate synthetic anomalous data points"""
    synthetic = []
    
    # Generate some IPs not seen in training
    fake_ips = [f"10.0.0.{i}" for i in range(1, 6)]
    for ip in fake_ips:
        if ip not in ip_encoder.classes_:
            ip_encoder.classes_ = np.append(ip_encoder.classes_, ip)
    
    # Generate some user IDs not seen in training
    fake_users = [f"attacker_{i}" for i in range(1, 4)]
    for user in fake_users:
        if user not in user_encoder.classes_:
            user_encoder.classes_ = np.append(user_encoder.classes_, user)
    
    # Create synthetic anomalies
    num_anomalies = max(5, len(features) // 20)
    
    for _ in range(num_anomalies):
        anomaly = {
            'ip_encoded': np.random.choice([ip_encoder.transform(fake_ips)[0], 
                                         np.random.randint(0, len(ip_encoder.classes_))]),
            'user_encoded': np.random.choice([user_encoder.transform(fake_users)[0],
                                           np.random.randint(0, len(user_encoder.classes_))]),
            'result': 0,
            'hour': np.random.randint(0, 24),
            'minute': np.random.randint(0, 60),
            'day_of_week': np.random.randint(0, 7)
        }
        synthetic.append(anomaly)
    
    return pd.DataFrame(synthetic)

def get_anomaly_reason(row, score, threshold, ip_encoder, user_encoder):
    """Determine reasons for anomaly"""
    reasons = []
    if row['hour'] < 6 or row['hour'] > 20:
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

# ----------------- Flask Endpoints -----------------

@app.route('/healthz')
def health():
    """Simplified health check endpoint"""
    try:
        return jsonify({
            "status": "OK",
            "timestamp": datetime.utcnow().isoformat()
        }), 200
    except Exception as e:
        return jsonify({
            "status": "ERROR",
            "error": str(e)
        }), 500

@app.route('/train', methods=['POST'])
def train():
    """Train the anomaly detection model"""
    try:
        data = request.json
        if not data:
            return jsonify({"error": "No data provided"}), 400
            
        logs = pd.DataFrame(data)
        
        # Validate required columns
        required_columns = ['timestamp', 'user_id', 'ip_address', 'result']
        if not all(col in logs.columns for col in required_columns):
            return jsonify({"error": f"Missing required columns. Needed: {required_columns}"}), 400

        # Check failure count
        failure_count = len(logs[logs['result'].str.lower() == 'failure'])
        if failure_count == 0:
            app.logger.warning("Training data contains only successful attempts")

        # Load known IPs and encoders
        known_ips = load_known_ips()
        _, ip_encoder, user_encoder = load_model_and_encoders()

        # Update known IPs
        new_ips = set(logs['ip_address'].astype(str).unique())
        known_ips.update(new_ips)
        save_known_ips(known_ips)

        # Preprocess and train
        features = preprocess_logs(logs, ip_encoder, user_encoder, fit_encoders=True)
        
        if failure_count == 0:
            app.logger.info("Generating synthetic anomalies")
            synthetic_features = generate_synthetic_anomalies(features, ip_encoder, user_encoder)
            features = pd.concat([features, synthetic_features])

        model = train_model(features)
        save_model_and_encoders(model, ip_encoder, user_encoder)

        return jsonify({
            "message": "Model trained successfully!",
            "stats": {
                "num_samples": len(logs),
                "num_features": features.shape[1],
                "num_ips": len(known_ips),
                "num_users": len(user_encoder.classes_),
                "failure_count": failure_count,
                "synthetic_anomalies_added": len(features) - len(logs) if failure_count == 0 else 0
            }
        })
    except Exception as e:
        app.logger.error(f"Training error: {str(e)}")
        return jsonify({"error": f"Training failed: {str(e)}"}), 500

@app.route('/detect', methods=['POST'])
def detect_anomalies():
    """Detect anomalies in log data"""
    try:
        data = request.json
        if not data:
            return jsonify({"error": "No data provided"}), 400
            
        logs = pd.DataFrame(data)
        
        # Validate required columns
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

        # Get anomaly predictions
        anomaly_scores = model.decision_function(features)
        threshold = np.percentile(anomaly_scores, 10)
        is_anomaly = (
            (anomaly_scores < threshold) | 
            (logs['ip_address'].apply(lambda x: x not in known_ips))
        )

        results = []
        for i, row in logs.iterrows():
            result = {
                "timestamp": str(row["timestamp"]),
                "user_id": str(row["user_id"]),
                "ip_address": str(row["ip_address"]),
                "result": "success" if row["result"] == 1 else "failure",
                "is_anomaly": bool(is_anomaly[i]),
                "anomaly_score": float(anomaly_scores[i]),
                "unknown_ip": bool(row["ip_address"] not in known_ips),
                "reason": get_anomaly_reason(features.iloc[i], anomaly_scores[i], threshold, ip_encoder, user_encoder) if is_anomaly[i] else None
            }
            results.append(result)

        return jsonify({
            "results": results,
            "stats": {
                "total_logs": int(len(logs)),
                "anomalies_detected": int(sum(is_anomaly)),
                "unknown_ips": int(sum(row["ip_address"] not in known_ips for _, row in logs.iterrows())),
                "anomaly_threshold": float(threshold)
            }
        })
    except Exception as e:
        app.logger.error(f"Detection error: {str(e)}")
        return jsonify({"error": f"Detection failed: {str(e)}"}), 500

# ----------------- Entry Point -----------------

if __name__ == '__main__':
    print("Starting Flask application...")
    print(f"Host: 0.0.0.0, Port: 5000")
    
    # Ensure data directory exists
    os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
    print(f"Data directory ready: {os.path.dirname(MODEL_PATH)}")
    
    # Start the application
    try:
        app.run(host='0.0.0.0', port=5000, threaded=True)
    except Exception as e:
        print(f"Failed to start application: {str(e)}")
        raise