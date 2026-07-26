import os
import logging
from flask import Flask, render_template, jsonify
from database import init_db
from api import api_bp
from collector import fetch_and_record_metrics, sync_logs_to_github
from apscheduler.schedulers.background import BackgroundScheduler

app = Flask(__name__)
init_db(app)

# Configure detailed file logging to logs/server_telemetry.log
log_dir = os.path.join(app.root_path, 'logs')
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, 'server_telemetry.log')

file_handler = logging.FileHandler(log_file)
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(logging.Formatter('[%(asctime)s] %(levelname)s in %(module)s: %(message)s'))

app.logger.setLevel(logging.INFO)
app.logger.addHandler(file_handler)

root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
root_logger.addHandler(file_handler)

app.register_blueprint(api_bp)

# Background scheduler for polling metrics (15s) and syncing telemetry logs to GitHub (30s)
scheduler = BackgroundScheduler(daemon=True)

def run_collector_task():
    try:
        fetch_and_record_metrics(app)
    except Exception as e:
        app.logger.error(f"Collector task error: {e}")

def run_log_sync_task():
    try:
        sync_logs_to_github(app)
    except Exception as e:
        app.logger.error(f"Log sync task error: {e}")

with app.app_context():
    fetch_and_record_metrics(app)

scheduler.add_job(run_collector_task, 'interval', seconds=15)
scheduler.add_job(run_log_sync_task, 'interval', seconds=30)
scheduler.start()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/health')
def health():
    return jsonify({'status': 'healthy', 'service': 'Unbound Analytics Dashboard', 'port': 81})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 81))
    app.logger.info(f"Starting Unbound Analytics Dashboard on 0.0.0.0:{port}")
    app.run(host='0.0.0.0', port=port, debug=False)
