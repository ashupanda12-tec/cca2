"""
deploy.py — Provision and launch the music service on ECS Fargate

Uses boto3 for all AWS operations and subprocess for Docker commands.
No AWS CLI installation required.

Usage (from backend/ecs/ directory):
    python deploy/deploy.py

Prerequisites:
    - Docker Desktop running (green indicator)
    - Active AWS Academy credentials in ~/.aws/credentials
    - pip install boto3  (already in requirements.txt)
"""

import base64
import subprocess
import sys
import time
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

# ── Deployment constants ───────────────────────────────────────────────────────
TARGET_REGION      = "us-east-1"
REGISTRY_REPO      = "music-backend"
CLUSTER_HANDLE     = "music-app-cluster"
SERVICE_HANDLE     = "music-backend-service"
TASK_BLUEPRINT     = "music-backend-ecs"
IMAGE_BUCKET_NAME  = "teststage2026"
CONTAINER_LOG_GRP  = "/ecs/music-backend"
INSTANCE_COUNT     = 1

# Directory containing this script's parent (backend/ecs/)
APP_ROOT = Path(__file__).resolve().parent.parent


# ── Utility functions ──────────────────────────────────────────────────────────

def shell(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
    """Execute a shell command, stream its output, raise on failure if check=True."""
    print(f"  $ {' '.join(cmd)}")
    return subprocess.run(cmd, check=check)


def announce(step_num: int, total: int, description: str) -> None:
    print(f"\n[{step_num}/{total}] {description}")


# ── Deployment orchestrator ────────────────────────────────────────────────────

def run_deployment() -> None:
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(" ECS Fargate Deployment — Music Subscription Service")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    TOTAL_STEPS = 10

    # Clients
    sts_client = boto3.client("sts",  region_name=TARGET_REGION)
    ecr_client = boto3.client("ecr",  region_name=TARGET_REGION)
    cw_client  = boto3.client("logs", region_name=TARGET_REGION)
    ec2_client = boto3.client("ec2",  region_name=TARGET_REGION)
    ecs_client = boto3.client("ecs",  region_name=TARGET_REGION)
    iam_client = boto3.client("iam",  region_name=TARGET_REGION)

    # ── 1. Resolve account identity ────────────────────────────────────────────
    announce(1, TOTAL_STEPS, "Resolving AWS account identity...")
    acct_id   = sts_client.get_caller_identity()["Account"]
    registry  = f"{acct_id}.dkr.ecr.{TARGET_REGION}.amazonaws.com"
    image_ref = f"{registry}/{REGISTRY_REPO}:latest"
    print(f"  Account  : {acct_id}")
    print(f"  Image URI: {image_ref}")

    # ── 2. Ensure ECR repository exists ────────────────────────────────────────
    announce(2, TOTAL_STEPS, f"Ensuring ECR repository '{REGISTRY_REPO}'...")
    try:
        ecr_client.create_repository(
            repositoryName=REGISTRY_REPO,
            imageScanningConfiguration={"scanOnPush": True},
        )
        print(f"  Repository created.")
    except ClientError as exc:
        if exc.response["Error"]["Code"] == "RepositoryAlreadyExistsException":
            print("  Already exists — skipped.")
        else:
            raise

    # ── 3. Authenticate Docker with ECR ────────────────────────────────────────
    announce(3, TOTAL_STEPS, "Authenticating Docker with ECR...")
    auth_data = ecr_client.get_authorization_token()["authorizationData"][0]
    raw_token = base64.b64decode(auth_data["authorizationToken"]).decode()
    docker_user, docker_pass = raw_token.split(":", 1)
    reg_endpoint = auth_data["proxyEndpoint"]
    shell(["docker", "login", "--username", docker_user,
           "--password", docker_pass, reg_endpoint])

    # ── 4. Build and push container image ──────────────────────────────────────
    announce(4, TOTAL_STEPS, "Building container image...")
    shell(["docker", "build", "-t", f"{REGISTRY_REPO}:latest", str(APP_ROOT)])
    print(f"\n  Tagging as {image_ref} ...")
    shell(["docker", "tag", f"{REGISTRY_REPO}:latest", image_ref])
    print("\n  Pushing to ECR...")
    shell(["docker", "push", image_ref])

    # ── 5. Create CloudWatch log group ─────────────────────────────────────────
    announce(5, TOTAL_STEPS, f"Creating log group '{CONTAINER_LOG_GRP}'...")
    try:
        cw_client.create_log_group(logGroupName=CONTAINER_LOG_GRP)
        print("  Created.")
    except ClientError as exc:
        if exc.response["Error"]["Code"] == "ResourceAlreadyExistsException":
            print("  Already exists — skipped.")
        else:
            raise

    # ── 6. Configure network security group ────────────────────────────────────
    announce(6, TOTAL_STEPS, "Configuring network security group...")
    vpc_resp = ec2_client.describe_vpcs(
        Filters=[{"Name": "isDefault", "Values": ["true"]}]
    )
    vpc_id = vpc_resp["Vpcs"][0]["VpcId"]
    print(f"  Default VPC: {vpc_id}")

    SG_LABEL = "music-backend-ecs-sg"
    existing_sgs = ec2_client.describe_security_groups(
        Filters=[
            {"Name": "group-name", "Values": [SG_LABEL]},
            {"Name": "vpc-id",     "Values": [vpc_id]},
        ]
    )["SecurityGroups"]

    if existing_sgs:
        sg_id = existing_sgs[0]["GroupId"]
        print(f"  Reusing security group: {sg_id}")
    else:
        new_sg = ec2_client.create_security_group(
            GroupName=SG_LABEL,
            Description="HTTP port 80 ingress for ECS music service",
            VpcId=vpc_id,
        )
        sg_id = new_sg["GroupId"]
        ec2_client.authorize_security_group_ingress(
            GroupId=sg_id,
            IpPermissions=[{
                "IpProtocol": "tcp",
                "FromPort":   80,
                "ToPort":     80,
                "IpRanges":   [{"CidrIp": "0.0.0.0/0"}],
            }],
        )
        print(f"  Created security group: {sg_id}")

    subnet_resp = ec2_client.describe_subnets(
        Filters=[
            {"Name": "vpc-id",       "Values": [vpc_id]},
            {"Name": "defaultForAz", "Values": ["true"]},
        ]
    )
    subnet_ids = [s["SubnetId"] for s in subnet_resp["Subnets"]]
    print(f"  Subnets: {subnet_ids}")

    # ── 7. Register task definition ────────────────────────────────────────────
    announce(7, TOTAL_STEPS, f"Registering task definition '{TASK_BLUEPRINT}'...")
    ecs_client.register_task_definition(
        family=TASK_BLUEPRINT,
        taskRoleArn=      f"arn:aws:iam::{acct_id}:role/LabRole",
        executionRoleArn= f"arn:aws:iam::{acct_id}:role/LabRole",
        networkMode="awsvpc",
        requiresCompatibilities=["FARGATE"],
        cpu="256",
        memory="512",
        containerDefinitions=[{
            "name":      "music-svc",
            "image":     image_ref,
            "essential": True,
            "portMappings": [{"containerPort": 80, "protocol": "tcp"}],
            "environment": [
                {"name": "AWS_DEFAULT_REGION", "value": TARGET_REGION},
                {"name": "S3_BUCKET",          "value": IMAGE_BUCKET_NAME},
                {"name": "FLASK_DEBUG",        "value": "false"},
            ],
            "logConfiguration": {
                "logDriver": "awslogs",
                "options": {
                    "awslogs-group":         CONTAINER_LOG_GRP,
                    "awslogs-region":        TARGET_REGION,
                    "awslogs-stream-prefix": "ecs",
                },
            },
            "healthCheck": {
                "command": [
                    "CMD-SHELL",
                    "python -c \"import urllib.request; "
                    "urllib.request.urlopen('http://localhost:80/health')\" || exit 1",
                ],
                "interval":    30,
                "timeout":     5,
                "retries":     3,
                "startPeriod": 15,
            },
        }],
    )
    print("  Task definition registered.")

    # ── 8. Create ECS cluster ──────────────────────────────────────────────────
    announce(8, TOTAL_STEPS, f"Ensuring cluster '{CLUSTER_HANDLE}'...")
    ecs_client.create_cluster(clusterName=CLUSTER_HANDLE)
    print(f"  Cluster ready.")

    # ── 8b. ECS service-linked role (required in AWS Academy) ─────────────────
    print("\n[8b/10] Ensuring ECS service-linked role...")
    try:
        iam_client.create_service_linked_role(AWSServiceName="ecs.amazonaws.com")
        print("  Created AWSServiceRoleForECS.")
        time.sleep(5)
    except ClientError as exc:
        code = exc.response["Error"]["Code"]
        msg  = exc.response["Error"]["Message"]
        if code in ("InvalidInput", "UnmodifiableEntityException") and "taken" in msg:
            print("  Already exists — skipped.")
        else:
            print(f"  Warning: {code}: {msg}")

    # ── 9. Create or update ECS service ───────────────────────────────────────
    announce(9, TOTAL_STEPS, f"Deploying ECS service '{SERVICE_HANDLE}'...")
    net_cfg = {
        "awsvpcConfiguration": {
            "subnets":        subnet_ids,
            "securityGroups": [sg_id],
            "assignPublicIp": "ENABLED",
        }
    }

    active_svcs = [
        s for s in ecs_client.describe_services(
            cluster=CLUSTER_HANDLE, services=[SERVICE_HANDLE]
        )["services"]
        if s["status"] == "ACTIVE"
    ]

    if active_svcs:
        print("  Service exists — updating task definition...")
        ecs_client.update_service(
            cluster=CLUSTER_HANDLE,
            service=SERVICE_HANDLE,
            taskDefinition=TASK_BLUEPRINT,
            desiredCount=INSTANCE_COUNT,
        )
    else:
        ecs_client.create_service(
            cluster=CLUSTER_HANDLE,
            serviceName=SERVICE_HANDLE,
            taskDefinition=TASK_BLUEPRINT,
            desiredCount=INSTANCE_COUNT,
            launchType="FARGATE",
            networkConfiguration=net_cfg,
        )
    print("  Service deployed.")

    # ── 10. Wait for running task and surface public IP ────────────────────────
    announce(10, TOTAL_STEPS, "Waiting for task to reach RUNNING state (~60s)...")
    public_ip = None

    for attempt in range(12):
        time.sleep(10)
        running_arns = ecs_client.list_tasks(
            cluster=CLUSTER_HANDLE,
            serviceName=SERVICE_HANDLE,
            desiredStatus="RUNNING",
        )["taskArns"]

        if not running_arns:
            print(f"  Attempt {attempt + 1}/12 — task not running yet...")
            continue

        task_info = ecs_client.describe_tasks(
            cluster=CLUSTER_HANDLE,
            tasks=[running_arns[0]],
        )["tasks"][0]

        eni_id = None
        for attachment in task_info.get("attachments", []):
            for detail in attachment.get("details", []):
                if detail["name"] == "networkInterfaceId":
                    eni_id = detail["value"]
                    break

        if not eni_id:
            print(f"  Attempt {attempt + 1}/12 — ENI not assigned yet...")
            continue

        eni_info = ec2_client.describe_network_interfaces(
            NetworkInterfaceIds=[eni_id]
        )["NetworkInterfaces"][0]

        public_ip = eni_info.get("Association", {}).get("PublicIp")
        if public_ip:
            break

        print(f"  Attempt {attempt + 1}/12 — public IP pending...")

    print("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(" Deployment complete!")

    if public_ip:
        print(f"\n Public IP   : {public_ip}")
        print(f" Health check: http://{public_ip}/health")
        print(f"\n Quick tests (PowerShell):")
        print(f'   Invoke-RestMethod -Uri "http://{public_ip}/health"')
        print(f'   Invoke-RestMethod -Uri "http://{public_ip}/music/query?artist=Taylor Swift"')
    else:
        print("\n Task still starting. Check ECS console in a moment:")
        print(f"  https://console.aws.amazon.com/ecs/v2/clusters/{CLUSTER_HANDLE}/services/{SERVICE_HANDLE}/tasks")

    print(f"\n CloudWatch logs:")
    print(f"  https://console.aws.amazon.com/cloudwatch/home?region={TARGET_REGION}"
          f"#logsV2:log-groups/log-group/%2Fecs%2Fmusic-backend")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")


if __name__ == "__main__":
    try:
        run_deployment()
    except KeyboardInterrupt:
        print("\nAborted.")
        sys.exit(1)
    except Exception as exc:
        print(f"\n[ERROR] {exc}")
        raise
