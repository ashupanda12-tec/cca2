#!/bin/bash
# =============================================================================
# bootstrap.sh  —  One-shot provisioning for the EC2 Flask service
#
# Target OS : Amazon Linux 2023 (AWS Academy default AMI)
# Caller    : ec2-user  (sudo required for system-level steps)
#
# What this script does
# ─────────────────────
#   1. Refreshes all OS packages
#   2. Installs Python 3.11, pip, and nginx
#   3. Copies the application source to /home/ec2-user/svc
#   4. Installs Python dependencies into the system Python
#   5. Writes an nginx reverse-proxy config (port 80 → port 5000)
#   6. Registers a systemd unit so gunicorn auto-restarts on failures/reboots
#   7. Brings both services online
#
# Usage
# ─────
#   # Upload the repo first:
#   scp -i key.pem -r Cloud_Computing_A2 ec2-user@<IP>:~
#
#   # Then SSH in and run:
#   chmod +x ~/Cloud_Computing_A2/backend/ec2/setup.sh
#   sudo ~/Cloud_Computing_A2/backend/ec2/setup.sh
# =============================================================================

set -euo pipefail

SVC_DIR="/home/ec2-user/svc"
SOURCE_DIR="/home/ec2-user/Cloud_Computing_A2/backend/ec2"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " EC2 Bootstrap — Music Subscription Service"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# ── Step 1: OS update ─────────────────────────────────────────────────────────
echo "[1/7] Refreshing system packages..."
dnf update -y

# ── Step 2: Runtime dependencies ─────────────────────────────────────────────
echo "[2/7] Installing Python 3.11, pip, and nginx..."
dnf install -y python3.11 python3.11-pip nginx

# ── Step 3: Deploy source code ────────────────────────────────────────────────
echo "[3/7] Copying application source to ${SVC_DIR}..."
mkdir -p "${SVC_DIR}"
cp -r "${SOURCE_DIR}/." "${SVC_DIR}/"
chown -R ec2-user:ec2-user "${SVC_DIR}"

# ── Step 4: Python packages ───────────────────────────────────────────────────
echo "[4/7] Installing Python dependencies..."
pip3.11 install -r "${SVC_DIR}/requirements.txt"

# ── Step 5: nginx configuration ──────────────────────────────────────────────
echo "[5/7] Writing nginx reverse-proxy configuration..."
rm -f /etc/nginx/conf.d/default.conf

cat > /etc/nginx/conf.d/music-svc.conf << 'NGINX_BLOCK'
server {
    listen 80 default_server;
    server_name _;

    location / {
        proxy_pass         http://127.0.0.1:5000;
        proxy_http_version 1.1;
        proxy_set_header   Host              $host;
        proxy_set_header   X-Real-IP         $remote_addr;
        proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
        proxy_connect_timeout 60s;
        proxy_read_timeout    60s;
    }
}
NGINX_BLOCK

nginx -t   # abort if config is invalid

# ── Step 6: systemd service unit ─────────────────────────────────────────────
echo "[6/7] Registering systemd service unit..."

cat > /etc/systemd/system/music-svc.service << UNIT_FILE
[Unit]
Description=Music Subscription Service (gunicorn)
After=network.target

[Service]
User=ec2-user
WorkingDirectory=${SVC_DIR}
Environment="AWS_DEFAULT_REGION=us-east-1"
Environment="FLASK_DEBUG=false"
ExecStart=/usr/local/bin/gunicorn \\
    --workers 4 \\
    --bind 127.0.0.1:5000 \\
    --access-logfile /var/log/music-svc-access.log \\
    --error-logfile  /var/log/music-svc-error.log \\
    app:app
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
UNIT_FILE

systemctl daemon-reload
systemctl enable music-svc

# ── Step 7: Start services ────────────────────────────────────────────────────
echo "[7/7] Starting gunicorn service and nginx..."
systemctl start  music-svc
systemctl enable nginx
systemctl start  nginx

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " Bootstrap complete!"
echo " Service live at: http://$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4)"
echo ""
echo " Liveness check : curl http://localhost/health"
echo " Service logs   : journalctl -u music-svc -f"
echo " nginx logs     : tail -f /var/log/nginx/error.log"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
