import os
import logging
from flask import Flask, render_template, jsonify
from database import init_db
from api import api_bp
from collector import fetch_and_record_metrics
from apscheduler.schedulers.background import BackgroundScheduler

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s: %(message)s')

app = Flask(__name__)
init_db(app)

app.register_blueprint(api_bp)

# Background scheduler for polling Unbound metrics
scheduler = BackgroundScheduler(daemon=True)
def run_collector_task():
    try:
        fetch_and_record_metrics(app)
    except Exception as e:
        app.logger.error(f"Collector error: {e}")

# Initial seed metric
with app.app_context():
    fetch_and_record_metrics(app)

scheduler.add_job(run_collector_task, 'interval', seconds=15)
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
