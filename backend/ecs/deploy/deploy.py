"""
deploy.py — Deploy the ECS backend to AWS Fargate (Windows-friendly, no AWS CLI needed)

Uses boto3 for all AWS operations and subprocess for Docker commands.

Usage (from backend/ecs/ directory):
    python deploy/deploy.py

Prerequisites:
    - Docker Desktop running
    - AWS credentials in ~/.aws/credentials (refreshed from AWS Academy)
    - pip install boto3  (already in requirements.txt)
"""

import base64
import json
import subprocess
import sys
import time
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

# ── Configuration ──────────────────────────────────────────────────────────────
REGION        = "us-east-1"
REPO_NAME     = "music-backend"
CLUSTER_NAME  = "music-app-cluster"
SERVICE_NAME  = "music-backend-service"
TASK_FAMILY   = "music-backend-ecs"
S3_BUCKET     = "teststage2026"
LOG_GROUP     = "/ecs/music-backend"
DESIRED_COUNT = 1

# Path to the backend/ecs/ directory (parent of this script's deploy/ folder)
ECS_DIR = Path(__file__).resolve().parent.parent

# ── Helpers ────────────────────────────────────────────────────────────────────

def run(cmd: list[str], check=True) -> subprocess.CompletedProcess:
    """Run a shell command, stream output, and optionally raise on failure."""
    print(f"  $ {' '.join(cmd)}")
    result = subprocess.run(cmd, check=check)
    return result


def step(n: int, total: int, msg: str):
    print(f"\n[{n}/{total}] {msg}")


# ── Main deployment ────────────────────────────────────────────────────────────

def main():
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(" ECS Fargate Deployment — Music Subscription App")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    TOTAL = 10

    # ── Boto3 clients ──────────────────────────────────────────────────────────
    sts    = boto3.client("sts",    region_name=REGION)
    ecr    = boto3.client("ecr",    region_name=REGION)
    logs   = boto3.client("logs",   region_name=REGION)
    ec2    = boto3.client("ec2",    region_name=REGION)
    ecs    = boto3.client("ecs",    region_name=REGION)
    iam    = boto3.client("iam",    region_name=REGION)

    # ── 1. Resolve account ID ──────────────────────────────────────────────────
    step(1, TOTAL, "Resolving AWS account ID...")
    account_id = sts.get_caller_identity()["Account"]
    ecr_uri    = f"{account_id}.dkr.ecr.{REGION}.amazonaws.com"
    image_uri  = f"{ecr_uri}/{REPO_NAME}:latest"
    print(f"  Account  : {account_id}")
    print(f"  Image URI: {image_uri}")

    # ── 2. Create ECR repository ───────────────────────────────────────────────
    step(2, TOTAL, f"Creating ECR repository '{REPO_NAME}'...")
    try:
        ecr.create_repository(
            repositoryName=REPO_NAME,
            imageScanningConfiguration={"scanOnPush": True},
        )
        print(f"  Created: {REPO_NAME}")
    except ClientError as e:
        if e.response["Error"]["Code"] == "RepositoryAlreadyExistsException":
            print("  Already exists — skipped.")
        else:
            raise

    # ── 3. Authenticate Docker to ECR ──────────────────────────────────────────
    step(3, TOTAL, "Authenticating Docker to ECR...")
    token    = ecr.get_authorization_token()["authorizationData"][0]
    raw      = base64.b64decode(token["authorizationToken"]).decode()
    username, password = raw.split(":", 1)
    registry = token["proxyEndpoint"]

    run(["docker", "login", "--username", username, "--password", password, registry])

    # ── 4. Build and push Docker image ─────────────────────────────────────────
    step(4, TOTAL, f"Building Docker image from {ECS_DIR} ...")
    run(["docker", "build", "-t", f"{REPO_NAME}:latest", str(ECS_DIR)])

    print(f"\n  Tagging as {image_uri} ...")
    run(["docker", "tag", f"{REPO_NAME}:latest", image_uri])

    print("\n  Pushing to ECR (this may take a minute)...")
    run(["docker", "push", image_uri])

    # ── 5. Create CloudWatch log group ─────────────────────────────────────────
    step(5, TOTAL, f"Creating CloudWatch log group '{LOG_GROUP}'...")
    try:
        logs.create_log_group(logGroupName=LOG_GROUP)
        print("  Created.")
    except ClientError as e:
        if e.response["Error"]["Code"] == "ResourceAlreadyExistsException":
            print("  Already exists — skipped.")
        else:
            raise

    # ── 6. Create security group ───────────────────────────────────────────────
    step(6, TOTAL, "Setting up security group...")
    vpcs    = ec2.describe_vpcs(Filters=[{"Name": "isDefault", "Values": ["true"]}])
    vpc_id  = vpcs["Vpcs"][0]["VpcId"]
    print(f"  Default VPC: {vpc_id}")

    SG_NAME = "music-backend-ecs-sg"
    existing = ec2.describe_security_groups(
        Filters=[
            {"Name": "group-name", "Values": [SG_NAME]},
            {"Name": "vpc-id",     "Values": [vpc_id]},
        ]
    )["SecurityGroups"]

    if existing:
        sg_id = existing[0]["GroupId"]
        print(f"  Using existing security group: {sg_id}")
    else:
        sg    = ec2.create_security_group(
            GroupName=SG_NAME,
            Description="Allow HTTP port 80 for ECS music backend",
            VpcId=vpc_id,
        )
        sg_id = sg["GroupId"]
        ec2.authorize_security_group_ingress(
            GroupId=sg_id,
            IpPermissions=[{
                "IpProtocol": "tcp",
                "FromPort":   80,
                "ToPort":     80,
                "IpRanges":   [{"CidrIp": "0.0.0.0/0"}],
            }],
        )
        print(f"  Created security group: {sg_id}")

    # Get default subnets
    subnets_resp = ec2.describe_subnets(
        Filters=[
            {"Name": "vpc-id",          "Values": [vpc_id]},
            {"Name": "defaultForAz",    "Values": ["true"]},
        ]
    )
    subnet_ids = [s["SubnetId"] for s in subnets_resp["Subnets"]]
    print(f"  Subnets: {subnet_ids}")

    # ── 7. Register ECS task definition ───────────────────────────────────────
    step(7, TOTAL, f"Registering ECS task definition '{TASK_FAMILY}'...")
    ecs.register_task_definition(
        family=TASK_FAMILY,
        taskRoleArn=      f"arn:aws:iam::{account_id}:role/LabRole",
        executionRoleArn= f"arn:aws:iam::{account_id}:role/LabRole",
        networkMode="awsvpc",
        requiresCompatibilities=["FARGATE"],
        cpu="256",
        memory="512",
        containerDefinitions=[{
            "name":      "music-backend",
            "image":     image_uri,
            "essential": True,
            "portMappings": [{"containerPort": 80, "protocol": "tcp"}],
            "environment": [
                {"name": "AWS_DEFAULT_REGION", "value": REGION},
                {"name": "S3_BUCKET",          "value": S3_BUCKET},
                {"name": "FLASK_DEBUG",        "value": "false"},
            ],
            "logConfiguration": {
                "logDriver": "awslogs",
                "options": {
                    "awslogs-group":         LOG_GROUP,
                    "awslogs-region":        REGION,
                    "awslogs-stream-prefix": "ecs",
                },
            },
            "healthCheck": {
                "command":     ["CMD-SHELL", "python -c \"import urllib.request; urllib.request.urlopen('http://localhost:80/health')\" || exit 1"],
                "interval":    30,
                "timeout":     5,
                "retries":     3,
                "startPeriod": 15,
            },
        }],
    )
    print("  Registered.")

    # ── 8. Create ECS cluster ──────────────────────────────────────────────────
    step(8, TOTAL, f"Creating ECS cluster '{CLUSTER_NAME}'...")
    ecs.create_cluster(clusterName=CLUSTER_NAME)
    print(f"  Cluster ready: {CLUSTER_NAME}")

    # ── 8b. Ensure ECS service-linked role exists ──────────────────────────────
    # AWS Academy accounts don't auto-create this role on first ECS use.
    # create_service_linked_role is allowed even under Academy IAM restrictions.
    print("\n[8b/10] Ensuring ECS service-linked role exists...")
    try:
        iam.create_service_linked_role(AWSServiceName="ecs.amazonaws.com")
        print("  Created AWSServiceRoleForECS.")
        time.sleep(5)  # give IAM a moment to propagate the new role
    except ClientError as e:
        code = e.response["Error"]["Code"]
        msg  = e.response["Error"]["Message"]
        if code == "InvalidInput" and "has been taken" in msg:
            print("  AWSServiceRoleForECS already exists — skipped.")
        elif code == "UnmodifiableEntityException":
            print("  AWSServiceRoleForECS already exists — skipped.")
        else:
            print(f"  Warning: could not create service-linked role ({code}: {msg})")
            print("  Continuing — role may already exist under a different name.")

    # ── 9. Create or update ECS service ───────────────────────────────────────
    step(9, TOTAL, f"Creating ECS Fargate service '{SERVICE_NAME}'...")
    network_config = {
        "awsvpcConfiguration": {
            "subnets":       subnet_ids,
            "securityGroups": [sg_id],
            "assignPublicIp": "ENABLED",
        }
    }

    existing_services = ecs.describe_services(
        cluster=CLUSTER_NAME,
        services=[SERVICE_NAME],
    )["services"]

    active = [s for s in existing_services if s["status"] == "ACTIVE"]

    if active:
        print("  Service already exists — updating task definition...")
        ecs.update_service(
            cluster=CLUSTER_NAME,
            service=SERVICE_NAME,
            taskDefinition=TASK_FAMILY,
            desiredCount=DESIRED_COUNT,
        )
    else:
        ecs.create_service(
            cluster=CLUSTER_NAME,
            serviceName=SERVICE_NAME,
            taskDefinition=TASK_FAMILY,
            desiredCount=DESIRED_COUNT,
            launchType="FARGATE",
            networkConfiguration=network_config,
        )
    print("  Service deployed.")

    # ── 10. Wait for task and print public IP ──────────────────────────────────
    step(10, TOTAL, "Waiting for task to reach RUNNING state (~60s)...")
    public_ip = None

    for attempt in range(12):  # wait up to 2 minutes
        time.sleep(10)
        tasks = ecs.list_tasks(
            cluster=CLUSTER_NAME,
            serviceName=SERVICE_NAME,
            desiredStatus="RUNNING",
        )["taskArns"]

        if not tasks:
            print(f"  Attempt {attempt + 1}/12 — task not running yet...")
            continue

        task_detail = ecs.describe_tasks(
            cluster=CLUSTER_NAME,
            tasks=[tasks[0]],
        )["tasks"][0]

        # Find the ENI attached to the task
        eni_id = None
        for attachment in task_detail.get("attachments", []):
            for detail in attachment.get("details", []):
                if detail["name"] == "networkInterfaceId":
                    eni_id = detail["value"]
                    break

        if not eni_id:
            print(f"  Attempt {attempt + 1}/12 — ENI not assigned yet...")
            continue

        eni = ec2.describe_network_interfaces(
            NetworkInterfaceIds=[eni_id]
        )["NetworkInterfaces"][0]

        public_ip = eni.get("Association", {}).get("PublicIp")
        if public_ip:
            break

        print(f"  Attempt {attempt + 1}/12 — public IP not assigned yet...")

    print("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(" Deployment complete!")
    print()

    if public_ip:
        print(f" Public IP   : {public_ip}")
        print(f" Health check: http://{public_ip}/health")
        print()
        print(" Test commands (PowerShell):")
        print(f'   Invoke-RestMethod -Uri "http://{public_ip}/health"')
        print(f'   Invoke-RestMethod -Uri "http://{public_ip}/music/query?artist=Taylor Swift"')
    else:
        print(" Task is still starting. Check the ECS console in a minute:")
        print(f"  https://console.aws.amazon.com/ecs/v2/clusters/{CLUSTER_NAME}/services/{SERVICE_NAME}/tasks")

    print()
    print(" CloudWatch logs:")
    print(f"  https://console.aws.amazon.com/cloudwatch/home?region={REGION}#logsV2:log-groups/log-group/%2Fecs%2Fmusic-backend")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nAborted.")
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] {e}")
        raise
