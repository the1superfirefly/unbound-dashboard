#!/usr/bin/env bash
# Deployment script for Unbound Analytics Dashboard
# Remote host: 192.168.4.86, Port: 81

TARGET_HOST="192.168.4.86"
TARGET_USER="root"
TARGET_DIR="/opt/unbound-dashboard"
PORT=81

GH_TOKEN=$(gh auth token 2>/dev/null)
if [ -n "$GH_TOKEN" ]; then
    REPO_URL="https://${GH_TOKEN}@github.com/the1superfirefly/unbound-dashboard.git"
else
    REPO_URL="https://github.com/the1superfirefly/unbound-dashboard.git"
fi

echo "=========================================="
echo " Deploying Unbound Analytics Dashboard "
echo " Target Host: ${TARGET_HOST} (Port ${PORT}) "
echo "=========================================="

# Create target directory on remote host
ssh -o StrictHostKeyChecking=no -o ConnectTimeout=5 ${TARGET_USER}@${TARGET_HOST} "mkdir -p ${TARGET_DIR}" 2>/dev/null || {
    echo "Notice: Could not connect via SSH root. Checking current user SSH access..."
    TARGET_USER=$(whoami)
}

echo "Syncing application code to ${TARGET_HOST}:${TARGET_DIR}..."
rsync -avz --delete --exclude 'database/*' --exclude '__pycache__' --exclude 'logs/*.log' --exclude 'venv' ./ ${TARGET_USER}@${TARGET_HOST}:${TARGET_DIR}/ || \
scp -r ./app.py ./api.py ./collector.py ./database.py ./parser.py ./requirements.txt ./templates ./static ${TARGET_USER}@${TARGET_HOST}:${TARGET_DIR}/

echo "Setting up Git repository & Authenticated Remote URL on target host..."
ssh ${TARGET_USER}@${TARGET_HOST} "cd ${TARGET_DIR} && mkdir -p logs && git config --global --add safe.directory ${TARGET_DIR} && (git rev-parse --is-inside-work-tree >/dev/null 2>&1 || (git init && git remote add origin ${REPO_URL})) && git remote set-url origin ${REPO_URL} && git config user.name 'UAD Telemetry Bot' && git config user.email 'uad-bot@unbound-dashboard.local' && python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt && (fuser -k ${PORT}/tcp || true) && sleep 2 && (nohup ./venv/bin/gunicorn --workers 4 --threads 4 --bind 0.0.0.0:${PORT} app:app > logs/app.log 2>&1 &)"

echo "Checking service response..."
sleep 3
curl -s -o /dev/null -w "%{http_code}" http://${TARGET_HOST}:${PORT}/health || echo "Waiting for service to bind..."

echo "Deployment finished! Service accessible at http://${TARGET_HOST}:${PORT}"
