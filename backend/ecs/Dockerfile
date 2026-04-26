# ─────────────────────────────────────────────────────────────────────────────
# Dockerfile — Music Subscription App (ECS/Fargate backend)
#
# Build:  docker build -t music-backend .
# Run:    docker run -p 80:80 \
#           -e AWS_DEFAULT_REGION=us-east-1 \
#           -e S3_BUCKET=your-bucket-name \
#           -v ~/.aws:/root/.aws:ro \
#           music-backend
#
# In production (ECS Fargate) the task role (LabRole) supplies credentials
# automatically — the ~/.aws mount is only needed for local testing.
# ─────────────────────────────────────────────────────────────────────────────

FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install dependencies first (separate layer → cached unless requirements change)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY . .

# Port 80 — gunicorn binds here directly (no nginx needed in the container;
# ECS Fargate exposes this port via the task's public IP and security group)
EXPOSE 80

# Run gunicorn on port 80.
# Fargate tasks run as root inside the container, so binding to port 80 is fine.
# Workers = 4 is a reasonable default for a t3.micro-equivalent vCPU allocation.
CMD ["gunicorn", \
     "--workers", "4", \
     "--bind", "0.0.0.0:80", \
     "--access-logfile", "-", \
     "--error-logfile", "-", \
     "app:app"]
