import json
import logging
from datetime import datetime
from flask import Flask, request, jsonify

app = Flask(__name__)

# Disable Flask's default HTTP access logs
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)  # Set to ERROR or higher to suppress lower level logs

# Configure custom logging for authentication logs
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger()

# Mock users database for authentication
users_db = {
    "user_1": "password1",
    "user_2": "password2",
    "user_3": "password3"
}

# Function to log authentication attempts
def log_authentication(user_id, ip_address, result):
    log_entry = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "user_id": user_id,
        "ip_address": ip_address,
        "result": result
    }
    logger.info(json.dumps(log_entry))  # Log the entry as a JSON string

# Login endpoint
@app.route('/login', methods=['POST'])
def login():
    data = request.json
    username = data.get("username")
    password = data.get("password")
    ip_address = request.remote_addr  # Get the IP address of the client
    
    if username in users_db and users_db[username] == password:
        log_authentication(username, ip_address, "success")
        return jsonify({"message": "Login successful"}), 200
    else:
        log_authentication(username, ip_address, "failure")
        return jsonify({"message": "Invalid credentials"}), 401

# Start the Flask app
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
