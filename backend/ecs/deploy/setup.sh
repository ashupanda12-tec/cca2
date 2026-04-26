#!/bin/bash
# =============================================================================
# deploy/setup.sh — Deploy the ECS backend to AWS Fargate
#
# What this script does (in order):
#   1.  Resolves your AWS account ID from the current credentials
#   2.  Creates an ECR repository (if it doesn't exist)
#   3.  Authenticates Docker to ECR
#   4.  Builds the Docker image and pushes it to ECR
#   5.  Creates a CloudWatch log group for ECS container logs
#   6.  Creates a VPC security group that allows inbound HTTP on port 80
#   7.  Fills in the task-definition.json template and registers it with ECS
#   8.  Creates an ECS cluster (if it doesn't exist)
#   9.  Creates an ECS Fargate service with a public IP
#   10. Prints the public IP of the running task
#
# Prerequisites:
#   - AWS CLI installed and configured with active Academy credentials
#   - Docker Desktop running
#   - Run from the backend/ecs/ directory:
#       chmod +x deploy/setup.sh
#       ./deploy/setup.sh
#
# To customise:
#   Export any of the variables below before running, e.g.:
#       export S3_BUCKET=my-own-bucket ./deploy/setup.sh
# =============================================================================

set -euo pipefail

# ── Configurable variables ────────────────────────────────────────────────────
REGION="${AWS_DEFAULT_REGION:-us-east-1}"
REPO_NAME="${ECR_REPO:-music-backend}"
CLUSTER_NAME="${ECS_CLUSTER:-music-app-cluster}"
SERVICE_NAME="${ECS_SERVICE:-music-backend-service}"
TASK_FAMILY="music-backend-ecs"
S3_BUCKET="${S3_BUCKET:-s4015064-music-artist-images}"
LOG_GROUP="/ecs/music-backend"
DESIRED_COUNT=1

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " ECS Fargate Deployment — Music Subscription App"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# ── 1. Resolve account ID ─────────────────────────────────────────────────────
echo "[1/10] Resolving AWS account ID..."
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
echo "       Account: ${ACCOUNT_ID}"
ECR_URI="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com"
IMAGE_URI="${ECR_URI}/${REPO_NAME}:latest"

# ── 2. Create ECR repository ──────────────────────────────────────────────────
echo "[2/10] Creating ECR repository '${REPO_NAME}' (if not exists)..."
aws ecr describe-repositories --repository-names "${REPO_NAME}" \
    --region "${REGION}" > /dev/null 2>&1 || \
aws ecr create-repository \
    --repository-name "${REPO_NAME}" \
    --region "${REGION}" \
    --image-scanning-configuration scanOnPush=true \
    --output text > /dev/null
echo "       ECR URI: ${IMAGE_URI}"

# ── 3. Authenticate Docker to ECR ────────────────────────────────────────────
echo "[3/10] Authenticating Docker to ECR..."
aws ecr get-login-password --region "${REGION}" | \
    docker login --username AWS --password-stdin "${ECR_URI}"

# ── 4. Build and push Docker image ───────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(dirname "${SCRIPT_DIR}")"

echo "[4/10] Building Docker image from ${APP_DIR}..."
docker build -t "${REPO_NAME}:latest" "${APP_DIR}"
docker tag "${REPO_NAME}:latest" "${IMAGE_URI}"
echo "       Pushing to ECR..."
docker push "${IMAGE_URI}"

# ── 5. Create CloudWatch log group ───────────────────────────────────────────
echo "[5/10] Creating CloudWatch log group '${LOG_GROUP}'..."
aws logs create-log-group \
    --log-group-name "${LOG_GROUP}" \
    --region "${REGION}" 2>/dev/null || echo "       (already exists — skipped)"

# ── 6. Create security group ──────────────────────────────────────────────────
echo "[6/10] Setting up security group..."
VPC_ID=$(aws ec2 describe-vpcs \
    --filters "Name=isDefault,Values=true" \
    --query "Vpcs[0].VpcId" \
    --output text \
    --region "${REGION}")
echo "       Default VPC: ${VPC_ID}"

SG_NAME="music-backend-ecs-sg"
EXISTING_SG=$(aws ec2 describe-security-groups \
    --filters "Name=group-name,Values=${SG_NAME}" "Name=vpc-id,Values=${VPC_ID}" \
    --query "SecurityGroups[0].GroupId" \
    --output text \
    --region "${REGION}" 2>/dev/null || echo "None")

if [ "${EXISTING_SG}" = "None" ] || [ -z "${EXISTING_SG}" ]; then
    SG_ID=$(aws ec2 create-security-group \
        --group-name "${SG_NAME}" \
        --description "Allow HTTP port 80 for ECS music backend" \
        --vpc-id "${VPC_ID}" \
        --region "${REGION}" \
        --query "GroupId" \
        --output text)
    aws ec2 authorize-security-group-ingress \
        --group-id "${SG_ID}" \
        --protocol tcp \
        --port 80 \
        --cidr 0.0.0.0/0 \
        --region "${REGION}" > /dev/null
    echo "       Created security group: ${SG_ID}"
else
    SG_ID="${EXISTING_SG}"
    echo "       Using existing security group: ${SG_ID}"
fi

# Get default subnets
SUBNETS=$(aws ec2 describe-subnets \
    --filters "Name=vpc-id,Values=${VPC_ID}" "Name=defaultForAz,Values=true" \
    --query "Subnets[*].SubnetId" \
    --output text \
    --region "${REGION}" | tr '\t' ',')
echo "       Subnets: ${SUBNETS}"

# ── 7. Register ECS task definition ──────────────────────────────────────────
echo "[7/10] Registering ECS task definition '${TASK_FAMILY}'..."

# Render the template by substituting placeholders
TASK_DEF=$(cat "${SCRIPT_DIR}/task-definition.json" | \
    sed "s|<ACCOUNT_ID>|${ACCOUNT_ID}|g" | \
    sed "s|<ECR_IMAGE_URI>|${IMAGE_URI}|g" | \
    sed "s|s4015064-music-artist-images|${S3_BUCKET}|g" | \
    python3 -c "
import sys, json
# Strip the 'comment' field — AWS rejects unknown top-level keys
d = json.load(sys.stdin)
d.pop('comment', None)
print(json.dumps(d))
")

aws ecs register-task-definition \
    --cli-input-json "${TASK_DEF}" \
    --region "${REGION}" \
    --query "taskDefinition.taskDefinitionArn" \
    --output text

# ── 8. Create ECS cluster ─────────────────────────────────────────────────────
echo "[8/10] Creating ECS cluster '${CLUSTER_NAME}' (if not exists)..."
aws ecs create-cluster \
    --cluster-name "${CLUSTER_NAME}" \
    --region "${REGION}" \
    --output text > /dev/null 2>&1 || true
echo "       Cluster: ${CLUSTER_NAME}"

# ── 9. Create or update ECS service ──────────────────────────────────────────
echo "[9/10] Creating ECS Fargate service '${SERVICE_NAME}'..."

NETWORK_CONFIG="awsvpcConfiguration={subnets=[${SUBNETS}],securityGroups=[${SG_ID}],assignPublicIp=ENABLED}"

SERVICE_EXISTS=$(aws ecs describe-services \
    --cluster "${CLUSTER_NAME}" \
    --services "${SERVICE_NAME}" \
    --region "${REGION}" \
    --query "services[?status=='ACTIVE'].serviceName" \
    --output text 2>/dev/null || echo "")

if [ -n "${SERVICE_EXISTS}" ]; then
    echo "       Service already exists — updating task definition..."
    aws ecs update-service \
        --cluster "${CLUSTER_NAME}" \
        --service "${SERVICE_NAME}" \
        --task-definition "${TASK_FAMILY}" \
        --desired-count "${DESIRED_COUNT}" \
        --region "${REGION}" \
        --output text > /dev/null
else
    aws ecs create-service \
        --cluster "${CLUSTER_NAME}" \
        --service-name "${SERVICE_NAME}" \
        --task-definition "${TASK_FAMILY}" \
        --desired-count "${DESIRED_COUNT}" \
        --launch-type FARGATE \
        --network-configuration "${NETWORK_CONFIG}" \
        --region "${REGION}" \
        --output text > /dev/null
fi

# ── 10. Wait and print public IP ──────────────────────────────────────────────
echo "[10/10] Waiting for task to reach RUNNING state (~30s)..."
sleep 30

TASK_ARN=$(aws ecs list-tasks \
    --cluster "${CLUSTER_NAME}" \
    --service-name "${SERVICE_NAME}" \
    --desired-status RUNNING \
    --region "${REGION}" \
    --query "taskArns[0]" \
    --output text 2>/dev/null || echo "")

if [ -z "${TASK_ARN}" ] || [ "${TASK_ARN}" = "None" ]; then
    echo ""
    echo "  Task is still starting. Check the console in a minute:"
    echo "  https://console.aws.amazon.com/ecs/v2/clusters/${CLUSTER_NAME}/services/${SERVICE_NAME}/tasks"
else
    ENI_ID=$(aws ecs describe-tasks \
        --cluster "${CLUSTER_NAME}" \
        --tasks "${TASK_ARN}" \
        --region "${REGION}" \
        --query "tasks[0].attachments[0].details[?name=='networkInterfaceId'].value" \
        --output text 2>/dev/null || echo "")

    PUBLIC_IP=$(aws ec2 describe-network-interfaces \
        --network-interface-ids "${ENI_ID}" \
        --region "${REGION}" \
        --query "NetworkInterfaces[0].Association.PublicIp" \
        --output text 2>/dev/null || echo "pending")

    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo " Deployment complete!"
    echo ""
    echo " Public IP  : ${PUBLIC_IP}"
    echo " Health check: curl http://${PUBLIC_IP}/health"
    echo " Login test :"
    echo "   curl -X POST http://${PUBLIC_IP}/auth/login \\"
    echo "     -H 'Content-Type: application/json' \\"
    echo "     -d '{\"email\":\"your-seed@student.rmit.edu.au\",\"password\":\"012345\"}'"
    echo ""
    echo " ECS Console:"
    echo "   https://console.aws.amazon.com/ecs/v2/clusters/${CLUSTER_NAME}/services/${SERVICE_NAME}"
    echo " CloudWatch Logs:"
    echo "   https://console.aws.amazon.com/cloudwatch/home?region=${REGION}#logsV2:log-groups/log-group/%2Fecs%2Fmusic-backend"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
fi
