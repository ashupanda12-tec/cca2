"""
app.py

Entry point for the EC2 Flask backend.

Architecture
────────────
Requests arrive at port 80 via nginx (reverse proxy) → forwarded to gunicorn
on 127.0.0.1:5000 → dispatched to the appropriate Blueprint route.

Blueprints:
  /auth          — login, register, logout
  /music         — song query
  /subscriptions — subscribe, remove, list
  /health        — liveness probe

Run locally (development):
    python app.py

Run on EC2 (production, via systemd):
    gunicorn -w 4 -b 127.0.0.1:5000 app:app
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
