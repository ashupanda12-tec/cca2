"""
app.py

Entry point for the ECS Flask backend.

Architecture
────────────
This is the same Flask application as the EC2 backend, packaged as a Docker
container for deployment on Amazon ECS (Fargate).

Unlike the EC2 deployment (which uses nginx → gunicorn), here gunicorn binds
directly to 0.0.0.0:80 inside the container.  There is no nginx needed —
ECS assigns a public IP to the Fargate task and the security group exposes
port 80 directly to the internet.

Blueprints:
  /auth          — login, register, logout
  /music         — song query
  /subscriptions — subscribe, remove, list
  /health        — liveness probe (also used as ECS health check)

Run locally with Docker Compose:
    docker compose up

Run on ECS (Fargate):
    See deploy/setup.sh
"""

from flask import Flask
from flask_cors import CORS

import config
from routes.auth          import auth_bp
from routes.music         import music_bp
from routes.subscriptions import subscriptions_bp

# ── App factory ────────────────────────────────────────────────────────────────
app = Flask(__name__)
app.secret_key = config.SECRET_KEY

# CORS: allow the frontend (S3 static site or any origin during dev) to call
# this API.  In production you should restrict origins to your frontend domain.
CORS(app, supports_credentials=True, origins="*")

# ── Register blueprints ────────────────────────────────────────────────────────
app.register_blueprint(auth_bp,          url_prefix="/auth")
app.register_blueprint(music_bp,         url_prefix="/music")
app.register_blueprint(subscriptions_bp, url_prefix="/subscriptions")


# ── Health check ───────────────────────────────────────────────────────────────
@app.route("/health")
def health():
    return {"status": "ok"}, 200


# ── Dev entry point ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=config.DEBUG)
