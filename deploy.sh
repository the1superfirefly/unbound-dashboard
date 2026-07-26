#!/usr/bin/env bash
# Deployment script for Unbound Analytics Dashboard
# Remote host: 192.168.4.86, Port: 81

TARGET_HOST="192.168.4.86"
TARGET_USER="root"
TARGET_DIR="/opt/unbound-dashboard"
PORT=81

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
rsync -avz --exclude 'database/*.db' --exclude '__pycache__' --exclude '.git' ./ ${TARGET_USER}@${TARGET_HOST}:${TARGET_DIR}/ || \
scp -r ./app.py ./api.py ./collector.py ./database.py ./parser.py ./requirements.txt ./templates ./static ${TARGET_USER}@${TARGET_HOST}:${TARGET_DIR}/

echo "Setting up Python environment and running service on Port ${PORT}..."
ssh ${TARGET_USER}@${TARGET_HOST} "cd ${TARGET_DIR} && python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt && nohup python3 app.py > logs/app.log 2>&1 &"

echo "Deployment finished! Service accessible at http://${TARGET_HOST}:${PORT}"
