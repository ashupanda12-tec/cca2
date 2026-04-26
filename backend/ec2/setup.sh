#!/bin/bash
# =============================================================================
# setup.sh  —  EC2 bootstrap script for the Flask backend
#
# Target OS : Amazon Linux 2023 (default AWS Academy AMI)
# Run as    : ec2-user (or paste as EC2 User Data — runs as root)
#
# What this script does:
#   1. Updates system packages
#   2. Installs Python 3.11, pip, and nginx
#   3. Copies the backend code to /home/ec2-user/backend
#   4. Installs Python dependencies
#   5. Configures nginx as a reverse proxy (port 80 → gunicorn on 5000)
#   6. Creates a systemd service so the app restarts on reboot
#   7. Starts nginx and the Flask service
#
# Usage (after SSH-ing into the EC2 instance):
#   1. Upload this repo to the instance:
#        scp -i your-key.pem -r Cloud_Computing_A2 ec2-user@<EC2-IP>:~
#   2. Run this script:
#        chmod +x ~/Cloud_Computing_A2/backend/ec2/setup.sh
#        sudo ~/Cloud_Computing_A2/backend/ec2/setup.sh
# =============================================================================

set -euo pipefail

APP_DIR="/home/ec2-user/backend"
REPO_DIR="/home/ec2-user/Cloud_Computing_A2/backend/ec2"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " EC2 Backend Setup — Music Subscription App"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# ── 1. System update ──────────────────────────────────────────────────────────
echo "[1/7] Updating system packages..."
dnf update -y

# ── 2. Install Python 3.11, pip, nginx ───────────────────────────────────────
echo "[2/7] Installing Python 3.11, pip, and nginx..."
dnf install -y python3.11 python3.11-pip nginx

# ── 3. Copy backend code ──────────────────────────────────────────────────────
echo "[3/7] Copying backend code to ${APP_DIR}..."
mkdir -p "${APP_DIR}"
cp -r "${REPO_DIR}/." "${APP_DIR}/"
chown -R ec2-user:ec2-user "${APP_DIR}"

# ── 4. Install Python dependencies ────────────────────────────────────────────
echo "[4/7] Installing Python dependencies..."
pip3.11 install -r "${APP_DIR}/requirements.txt"

# ── 5. Configure nginx reverse proxy ─────────────────────────────────────────
echo "[5/7] Configuring nginx..."

# Remove default server block
rm -f /etc/nginx/conf.d/default.conf

cat > /etc/nginx/conf.d/flask-backend.conf << 'NGINX_CONF'
server {
    listen 80 default_server;
    server_name _;

    # Forward all traffic to gunicorn
    location / {
        proxy_pass         http://127.0.0.1:5000;
        proxy_http_version 1.1;
        proxy_set_header   Host              $host;
        proxy_set_header   X-Real-IP         $remote_addr;
        proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;

        # Timeout settings
        proxy_connect_timeout 60s;
        proxy_read_timeout    60s;
    }
}
NGINX_CONF

nginx -t  # validate config before restarting

# ── 6. Create systemd service ─────────────────────────────────────────────────
echo "[6/7] Creating systemd service..."

cat > /etc/systemd/system/flask-backend.service << SERVICE_CONF
[Unit]
Description=Music Subscription Flask Backend (gunicorn)
After=network.target

[Service]
User=ec2-user
WorkingDirectory=${APP_DIR}
Environment="AWS_DEFAULT_REGION=us-east-1"
Environment="FLASK_DEBUG=false"
ExecStart=/usr/local/bin/gunicorn \\
    --workers 4 \\
    --bind 127.0.0.1:5000 \\
    --access-logfile /var/log/flask-backend-access.log \\
    --error-logfile  /var/log/flask-backend-error.log \\
    app:app
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
SERVICE_CONF

systemctl daemon-reload
systemctl enable flask-backend

# ── 7. Start services ─────────────────────────────────────────────────────────
echo "[7/7] Starting services..."
systemctl start  flask-backend
systemctl enable nginx
systemctl start  nginx

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " Setup complete!"
echo " Backend is live on http://$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4)"
echo ""
echo " Health check:  curl http://localhost/health"
echo " Service logs:  journalctl -u flask-backend -f"
echo " Nginx logs:    tail -f /var/log/nginx/error.log"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
