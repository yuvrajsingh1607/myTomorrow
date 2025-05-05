import logging
import requests
from loguru import logger
from flask import Flask, jsonify, request
import time
from datetime import datetime
import json
import sys
from werkzeug.serving import WSGIRequestHandler

app = Flask(__name__)

# Disable all Flask/Werkzeug logging
logging.getLogger('werkzeug').disabled = True
app.logger.disabled = True

# Configure Werkzeug to not log requests
WSGIRequestHandler.log_request = lambda *args, **kwargs: None

# Loki configuration
LOKI_URL = "http://loki.default.svc.cluster.local:3100/loki/api/v1/push"

class LokiHandler:
    def write(self, message):
        try:
            # Only process properly formatted JSON messages
            if message.strip().startswith('{'):
                payload = {
                    "streams": [
                        {
                            "stream": {
                                "job": "flask-app",
                                "namespace": "flask-login"
                            },
                            "values": [
                                [str(int(time.time() * 1e9)), message.strip()]
                            ]
                        }
                    ]
                }
                headers = {"Content-Type": "application/json"}
                requests.post(LOKI_URL, json=payload, headers=headers, timeout=5)
        except Exception:
            pass  # Silently fail if Loki is unavailable

# Configure logging - only our JSON messages
logger.remove()
logger.add(sys.stdout, format="{message}", level="INFO")
logger.add(LokiHandler(), format="{message}", level="INFO")

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    user_id = data.get("username")
    password = data.get("password")
    ip_address = request.remote_addr
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    log_data = {
        "timestamp": timestamp,
        "user_id": user_id,
        "ip_address": ip_address,
        "result": "success" if user_id == "user_1" and password == "password1" else "failure"
    }

    # Log only the JSON message
    logger.info(json.dumps(log_data, separators=(',', ':')))
    
    if log_data["result"] == "success":
        return jsonify({"message": "Login successful"}), 200
    else:
        return jsonify({"message": "Login failed"}), 401

if __name__ == '__main__':
    # Run without any access logging
    app.run(debug=False, host='0.0.0.0', port=5000)