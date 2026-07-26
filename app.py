import os
import logging
import subprocess
from flask import Flask, render_template, jsonify
from database import init_db
from api import api_bp
from collector import init_scheduler, purge_orphan_metrics, fetch_and_record_metrics

app = Flask(__name__)

# Dynamically compute application version based on git commit count & short hash
def get_app_version():
    try:
        count = subprocess.check_output(["git", "rev-list", "--count", "HEAD"], text=True).strip()
        short_hash = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], text=True).strip()
        return f"v2.{count}.0-{short_hash}"
    except Exception:
        return "v2.1.0"

APP_VERSION = get_app_version()

@app.context_processor
def inject_version():
    return dict(version=APP_VERSION)

# Configure SQLite database path inside database/ directory
db_dir = os.path.join(app.root_path, 'database')
os.makedirs(db_dir, exist_ok=True)
db_path = os.path.join(db_dir, 'unbound_dashboard.db')
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize database schema
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

# Register API routes
app.register_blueprint(api_bp)

with app.app_context():
    purge_orphan_metrics(app)
    fetch_and_record_metrics(app)

# Start 1-second metric collection cycle & 30-second GitHub log sync
scheduler = init_scheduler(app)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/health')
def health():
    return jsonify({'status': 'healthy', 'service': 'Unbound Analytics Dashboard', 'version': APP_VERSION, 'port': 81})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 81))
    app.logger.info(f"Starting Unbound Analytics Dashboard {APP_VERSION} on 0.0.0.0:{port}")
    app.run(host='0.0.0.0', port=port, debug=False)
