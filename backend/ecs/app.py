"""
server.py  (ECS Fargate entry point)

Identical Flask application to the EC2 variant, packaged as a Docker image
for deployment on Amazon ECS Fargate.

Key difference from EC2
────────────────────────
On EC2 an nginx process sits in front of gunicorn and listens on port 80.
Here gunicorn binds directly to 0.0.0.0:80 inside the container — there is
no nginx layer. ECS assigns a public IP to the Fargate task and the security
group exposes port 80.

Module groups:
  /auth          —  credential routes
  /music         —  catalogue search
  /subscriptions —  user library management
  /health        —  ECS health-check probe

Local run (Python — no Docker required):
    python app.py

Local run with Docker Compose:
    docker compose up

ECS deployment:
    python deploy/deploy.py
"""

from flask import Flask
from flask_cors import CORS

import settings
from routes.credential_routes  import credential_bp
from routes.catalogue_routes   import catalogue_bp
from routes.library_routes     import library_bp

# ── Application setup ──────────────────────────────────────────────────────────
app = Flask(__name__)
app.secret_key = settings.APP_SECRET

CORS(app, supports_credentials=True, origins="*")

# ── Blueprints ─────────────────────────────────────────────────────────────────
app.register_blueprint(credential_bp, url_prefix="/auth")
app.register_blueprint(catalogue_bp,  url_prefix="/music")
app.register_blueprint(library_bp,    url_prefix="/subscriptions")


# ── Liveness probe ─────────────────────────────────────────────────────────────
@app.route("/health")
def liveness():
    return {"status": "ok"}, 200


# ── Direct runner ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=settings.DEV_MODE)
