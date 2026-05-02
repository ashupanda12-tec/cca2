"""
server.py  (entry point)

Gateway for the EC2-hosted REST service.

Request pipeline
────────────────
Inbound traffic hits nginx on port 80  →  nginx proxies to this process
on 127.0.0.1:5000  →  Flask routes the call to the correct module group.

Module groups registered:
  /auth          —  credential verification, account creation, session close
  /music         —  catalogue search
  /subscriptions —  user library management
  /health        —  liveness probe used by nginx and monitoring tools

Local start (dev):
    python app.py

EC2 production (via systemd unit):
    gunicorn -w 4 -b 127.0.0.1:5000 app:app
"""

from flask import Flask
from flask_cors import CORS

import settings
from routes.credential_routes  import credential_bp
from routes.catalogue_routes   import catalogue_bp
from routes.library_routes     import library_bp

# ── Initialise core application ────────────────────────────────────────────────
app = Flask(__name__)
app.secret_key = settings.APP_SECRET

# Allow cross-origin requests from the frontend (any origin during development;
# lock down to the S3 static-site domain in production).
CORS(app, supports_credentials=True, origins="*")

# ── Attach route modules ───────────────────────────────────────────────────────
app.register_blueprint(credential_bp, url_prefix="/auth")
app.register_blueprint(catalogue_bp,  url_prefix="/music")
app.register_blueprint(library_bp,    url_prefix="/subscriptions")


# ── Liveness probe ─────────────────────────────────────────────────────────────
@app.route("/health")
def liveness():
    return {"status": "ok"}, 200


# ── Standalone runner ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=settings.DEV_MODE)
