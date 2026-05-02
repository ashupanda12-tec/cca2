# ─────────────────────────────────────────────────────────────────────────────
# Dockerfile — Music Subscription Service (ECS Fargate)
#
# Build:   docker build -t music-svc .
# Run:     docker run -p 80:80 \
#            -e AWS_DEFAULT_REGION=us-east-1 \
#            -e S3_BUCKET=your-bucket \
#            -v ~/.aws:/root/.aws:ro \
#            music-svc
#
# In production the ECS task role (LabRole) injects credentials automatically.
# The ~/.aws mount is only needed for local testing via docker run.
# ─────────────────────────────────────────────────────────────────────────────

FROM python:3.11-slim

WORKDIR /app

# Install dependencies first — this layer is cached unless requirements change
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source after dependencies so code changes don't bust the cache
COPY . .

# gunicorn binds on port 80 directly; no nginx inside the container
EXPOSE 80

CMD ["gunicorn", \
     "--workers", "4", \
     "--bind", "0.0.0.0:80", \
     "--access-logfile", "-", \
     "--error-logfile", "-", \
     "app:app"]
