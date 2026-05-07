# Cloud-A2-146 — Sonata Music Subscription App

A cloud-native music subscription web application built on AWS as part of Cloud
Computing Assignment 2. Users can register, log in, search songs across a
DynamoDB dataset, and manage a personal subscription library. Artist images are
served from S3.

---

## Quick Start — Order of Operations

If you are setting this project up from scratch, follow every step in this exact order:

1. [Install prerequisites](#prerequisites)
2. [Configure the three required personal values](#before-you-start--required-configuration)
3. [Set up AWS credentials](#aws-credentials)
4. [Run the infrastructure scripts](#part-1--aws-infrastructure-setup) — DynamoDB + S3
5. Deploy a backend (pick one):
   - [Lambda + API Gateway](#part-2--lambda--api-gateway-backend-recommended) ← Recommended
   - [ECS Fargate](#part-3--ecs-fargate-backend)
6. [Deploy the frontend](#part-4--frontend-deployment)
7. [Verify everything works](#part-5--end-to-end-verification)

---

## Project Structure

```
Cloud-A2-146/
│
├── data_setup/                         # One-time AWS infrastructure scripts
│   ├── config.py                       # Shared config: region, table names, bucket
│   ├── create_tables.py                # Creates login, music, subscriptions tables
│   ├── seed_login_table.py             # Inserts 10 seed login users
│   ├── load_music_table.py             # Loads 137 songs into DynamoDB
│   ├── upload_artist_images.py         # Downloads images → uploads to S3
│   ├── update_music_s3_keys.py         # Writes S3 image paths back to DynamoDB
│   ├── verify_system.py                # End-to-end test: login, query, subscribe
│   └── 2026a2_songs.json               # Source music dataset (137 songs)
│
├── lambda_backend/
│   ├── lambda_function.py              # ✅ Complete — single-file Lambda handler (fixed)
│   └── template.yaml                   # ✅ SAM template — API Gateway + Lambda
│
├── ecs_backend/                        # ✅ Complete — Dockerised Flask app
│   ├── app.py                          # Flask routes (identical logic to Lambda)
│   ├── config.py                       # AWS constants
│   ├── requirements.txt                # flask, flask-cors, boto3
│   └── Dockerfile                      # Runs Flask on port 80
│
├── backend_flask/                      # ⚠️  EC2 Flask backend — INCOMPLETE
│   ├── app.py
│   ├── config.py
│   └── requirements.txt
│
└── frontend/                           # Static web UI — "Sonata"
    ├── login.html                      # Login page
    ├── register.html                   # Registration page
    ├── index.html                      # Main app (search + library)
    ├── login.js
    ├── register.js
    ├── app.js                          # All frontend logic
    └── config.js                       # ← YOU MUST UPDATE API_BASE_URL HERE
```

---

## ⚠️ Code Issues Fixed Before Deployment

The original `lambda_backend/lambda_function.py` had two bugs that would cause
silent crashes in production:

| Issue | Impact | Fix Applied |
|-------|--------|-------------|
| `ClientError` not imported from `botocore.exceptions` | Any DynamoDB error (throttle, auth failure, network) would crash the Lambda with an unhandled Python exception instead of returning a clean 500 | Added `from botocore.exceptions import ClientError` |
| No `try/except` around DynamoDB calls in any handler | Same crash behaviour — every route was unprotected | Wrapped every DynamoDB call in `try/except ClientError` returning a proper 500 response |
| `template.yaml` entirely missing | `sam build` and `sam deploy` cannot run without this file | Created `template.yaml` with all routes, CORS, and Outputs |

The fixed `lambda_function.py` and the new `template.yaml` are provided
alongside this README — replace the originals in `lambda_backend/` with these
before proceeding.

**ECS backend** (`ecs_backend/`) has no code bugs. The Flask error handling is
already in place. The only deployment risk is the ECS task IAM role — if it
does not have DynamoDB and S3 permissions, every API request will fail with
`AccessDeniedException`. This is covered in detail in Part 3.

---

## Prerequisites

Install all of the following before starting. Missing any one will cause a
specific part of the setup to fail.

### Required for everyone

| Tool | Minimum Version | Why It Is Needed | Install Link |
|------|----------------|------------------|--------------|
| Python | 3.10+ | Running data setup scripts and Lambda code locally | [python.org](https://www.python.org/downloads/) |
| pip | Latest | Installing Python packages | Bundled with Python |
| AWS CLI v2 | 2.x | Configuring credentials, creating S3 buckets, querying resources | [AWS CLI install guide](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html) |
| Git | Any | Cloning this repository | [git-scm.com](https://git-scm.com/) |

### Required for Lambda deployment

| Tool | Minimum Version | Why It Is Needed | Install Link |
|------|----------------|------------------|--------------|
| AWS SAM CLI | 1.100+ | Building and deploying the Lambda function and API Gateway via `template.yaml`. You cannot deploy Lambda without this. | [SAM CLI install guide](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html) |
| Docker Desktop | Latest | `sam build --use-container` packages dependencies inside a Lambda-compatible Docker container. SAM will refuse to build without Docker running. | [docker.com](https://www.docker.com/products/docker-desktop/) |

### Required for ECS deployment

| Tool | Minimum Version | Why It Is Needed | Install Link |
|------|----------------|------------------|--------------|
| Docker Desktop | Latest | Building the container image and pushing it to ECR | [docker.com](https://www.docker.com/products/docker-desktop/) |

### Verify your installs

Run these four commands and confirm they all return version numbers:

```bash
python --version      # Python 3.10.x or higher
aws --version         # aws-cli/2.x.x
sam --version         # SAM CLI, version 1.x.x
docker --version      # Docker version xx.x
```

### Install Python dependencies for the data setup scripts

```bash
cd data_setup
pip install boto3 requests
```

---

## AWS Credentials

All scripts and backends authenticate with AWS using credentials stored in
`~/.aws/credentials`. AWS Academy credentials expire when your lab session ends
and must be refreshed at the start of every new session.

### Setting up credentials (first time or after expiry)

**Step 1.** Open your AWS Academy Lab and click **Start Lab**.

**Step 2.** Click **AWS Details** in the top panel, then click **AWS CLI**.

**Step 3.** Click **Copy** on the credentials block.

**Step 4.** Paste the block into your credentials file, replacing all existing content:

- **Windows:** `C:\Users\<your-username>\.aws\credentials`
- **Mac/Linux:** `~/.aws/credentials`

The file must look exactly like this (your values will differ each session):

```ini
[default]
aws_access_key_id = ASIA...
aws_secret_access_key = wJalrXUtn...
aws_session_token = IQoJb3JpZ2...
```

**Step 5.** Verify the credentials work:

```bash
aws sts get-caller-identity
```

Expected output (account ID will differ):

```json
{
    "UserId": "AROA...",
    "Account": "123456789012",
    "Arn": "arn:aws:sts::123456789012:assumed-role/vocstartsoft/user..."
}
```

If you get `ExpiredTokenException` or `InvalidClientTokenId`, your lab session
has expired — go back to Step 1.

---

## Before You Start — Required Configuration

Three values in the codebase are specific to your environment and **must be
updated before running any scripts or deploying any backend**. Skipping this
will either cause scripts to fail or seed the wrong data.

### 1. S3 bucket name

S3 bucket names are globally unique across all of AWS. The current value in the
repo is:

```
music-app-images-kingston-4156256-2026
```

If another person is already using this name, create your own (e.g.
`s1234567-music-images-2026`) and update it in **all three locations**:

| File | Constant to change |
|------|--------------------|
| `data_setup/config.py` | `S3_BUCKET_NAME = "your-bucket-name"` |
| `ecs_backend/config.py` | `S3_BUCKET_NAME = "your-bucket-name"` |
| `lambda_backend/lambda_function.py` | `S3_BUCKET_NAME = "your-bucket-name"` |

All three must be identical.

### 2. Login seed user details

Open `data_setup/config.py` and update these two constants to reflect your
own student details before running `seed_login_table.py`:

```python
GROUP_BASE_STUDENT_ID = "s1234567"   # ← your RMIT student number
GROUP_BASE_NAME       = "GroupUser"  # ← display name prefix for seed accounts
```

This generates 10 seed accounts:

| Account | Email | Password |
|---------|-------|----------|
| 0 | s1234567+0@student.rmit.edu.au | 012345 |
| 1 | s1234567+1@student.rmit.edu.au | 123456 |
| 2 | s1234567+2@student.rmit.edu.au | 234567 |
| 3 | s1234567+3@student.rmit.edu.au | 345678 |
| 4 | s1234567+4@student.rmit.edu.au | 456789 |
| 5 | s1234567+5@student.rmit.edu.au | 567890 |
| 6 | s1234567+6@student.rmit.edu.au | 678901 |
| 7 | s1234567+7@student.rmit.edu.au | 789012 |
| 8 | s1234567+8@student.rmit.edu.au | 890123 |
| 9 | s1234567+9@student.rmit.edu.au | 901234 |

### 3. Frontend API URL

After deploying your backend, you will receive a URL. Open `frontend/config.js`
and update this line before uploading the frontend:

```javascript
// Lambda + API Gateway:
const API_BASE_URL = "https://<api-id>.execute-api.us-east-1.amazonaws.com/prod";

// ECS Fargate:
const API_BASE_URL = "http://<ecs-public-ip>";
```

---

## Part 1 — AWS Infrastructure Setup

These scripts are run **once** from your local machine. Run them in the order
shown. All commands assume you are inside the `data_setup/` directory.

### Step 1.1 — Create the S3 bucket

Create the bucket and make it publicly readable for images.

```bash
# Create the bucket (us-east-1 does not use --create-bucket-configuration)
aws s3api create-bucket \
  --bucket music-app-images-kingston-4156256-2026 \
  --region us-east-1

# Disable the default "block all public access" restriction
aws s3api put-public-access-block \
  --bucket music-app-images-kingston-4156256-2026 \
  --public-access-block-configuration \
  "BlockPublicAcls=false,IgnorePublicAcls=false,BlockPublicPolicy=false,RestrictPublicBuckets=false"
```

Create a file called `bucket-policy.json` in your current directory (replace
the bucket name if you changed it):

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "PublicReadImages",
      "Effect": "Allow",
      "Principal": "*",
      "Action": "s3:GetObject",
      "Resource": "arn:aws:s3:::music-app-images-kingston-4156256-2026/*"
    }
  ]
}
```

Apply the policy:

```bash
aws s3api put-bucket-policy \
  --bucket music-app-images-kingston-4156256-2026 \
  --policy file://bucket-policy.json
```

Verify the bucket exists and is reachable:

```bash
aws s3 ls s3://music-app-images-kingston-4156256-2026
```

No error = success (the output will be empty because the bucket is new).

### Step 1.2 — Create the DynamoDB tables

```bash
cd data_setup
python create_tables.py
```

Expected output:

```
Creating table 'login'...
Waiting for table 'login' to become active...
Table 'login' is now active.

Creating table 'music'...
Waiting for table 'music' to become active...
Table 'music' is now active.

Creating table 'subscriptions'...
Waiting for table 'subscriptions' to become active...
Table 'subscriptions' is now active.

All required tables are ready.
```

If a table already exists from a previous run you will see:
`Table 'login' already exists. Skipping creation.` — this is fine.

**Verify in the AWS Console:** DynamoDB → Tables. All three tables should show
status **Active**.

The table schemas:

| Table | Partition Key | Sort Key | Extra Indexes |
|-------|--------------|----------|---------------|
| `login` | `email` (String) | — | None |
| `music` | `artist` (String) | `title_year_album` (String) | LSI: `artist-year-album-title-lsi` on `year_album_title`; GSI: `title-artist-year-album-gsi` on `title` + `artist_year_album` |
| `subscriptions` | `email` (String) | `music_id` (String) | None |

### Step 1.3 — Seed the login table

Confirm you updated `GROUP_BASE_STUDENT_ID` in `config.py` first.

```bash
python seed_login_table.py
```

Expected output:

```
Successfully inserted 10 login records into the login table.

Inserted records:
{'email': 's1234567+0@student.rmit.edu.au', 'user_name': 'GroupUser0', 'password': '012345'}
{'email': 's1234567+1@student.rmit.edu.au', 'user_name': 'GroupUser1', 'password': '123456'}
...
{'email': 's1234567+9@student.rmit.edu.au', 'user_name': 'GroupUser9', 'password': '901234'}
```

### Step 1.4 — Load the music table

```bash
python load_music_table.py
```

Expected output:

```
Loaded 137 songs from 2026a2_songs.json.
Successfully inserted 137 songs into the music table.
```

### Step 1.5 — Upload artist images to S3

This script downloads each unique artist image from GitHub raw URLs and uploads
them into the `artists/` prefix of your S3 bucket. It creates a local
`temp_images/` folder during the process (already in `.gitignore`).

```bash
python upload_artist_images.py
```

Expected output:

```
Fetching unique images...
Found 67 unique images.

Uploaded: artists/TaylorSwift.jpg
Uploaded: artists/JackJohnson.jpg
Uploaded: artists/TheLumineers.jpg
...
All images processed.
```

This takes 1–3 minutes depending on your internet speed. If a specific image
fails to download, that artist's songs will show no image in the UI (non-fatal).

### Step 1.6 — Write S3 image keys back to DynamoDB

After the images are uploaded, this script scans every song record in DynamoDB
and writes the corresponding S3 key (e.g. `artists/TaylorSwift.jpg`) into the
`image_s3_key` field. Without this step, the backend cannot serve image URLs.

```bash
python update_music_s3_keys.py
```

Expected output:

```
Fetching all music items from DynamoDB...
Found 137 music items.

Updated: Taylor Swift | Bad Blood#2014#1989 -> artists/TaylorSwift.jpg
Updated: Jack Johnson | Banana Pancakes#2005#In Between Dreams -> artists/JackJohnson.jpg
...
Finished updating image_s3_key for all music items.
```

---

## Part 2 — Lambda + API Gateway Backend (Recommended)

> ✅ This deployment path is complete and recommended. A single Lambda function
> handles all routes. API Gateway provides the public HTTPS endpoint. No servers
> to manage — AWS handles scaling automatically.

### Before starting this section

1. Copy the fixed `lambda_function.py` and new `template.yaml` (provided
   alongside this README) into your `lambda_backend/` folder, replacing the
   originals.

2. Confirm Docker Desktop is open and running:

```bash
docker info   # Should print engine details, not an error
sam --version # Should print SAM CLI version
```

### Step 2.1 — Get your LabRole ARN

Lambda functions in AWS Academy must use the pre-created `LabRole` IAM role.
You cannot create new IAM roles in Academy accounts.

1. In the AWS Console go to **IAM → Roles**
2. Search for `LabRole` and click it
3. Copy the **ARN** shown at the top. It looks like:

```
arn:aws:iam::123456789012:role/LabRole
```

Keep this ready — you need it in Step 2.3.

### Step 2.2 — Build the Lambda package

SAM packages your code inside a Docker container that replicates the Lambda
runtime. Docker Desktop must be running before you execute this.

```bash
cd lambda_backend
sam build --use-container
```

Expected output:

```
Building codeuri: . runtime: python3.10 metadata: {} architecture: x86_64
Running PythonPipBuilder:ResolveDependencies
Running PythonPipBuilder:CopySource

Build Succeeded

Built Artifacts  : .aws-sam/build
Built Template   : .aws-sam/build/template.yaml
```

> If `sam build` fails with `Error: Docker is not reachable`, Docker Desktop
> is not fully started yet. Wait for the whale icon to stop animating, then retry.

### Step 2.3 — Deploy to AWS (first time — interactive wizard)

```bash
sam deploy --guided \
  --parameter-overrides LabRoleArn=arn:aws:iam::<YOUR_ACCOUNT_ID>:role/LabRole
```

Replace `<YOUR_ACCOUNT_ID>` with your actual account ID (visible in the top-right
of the AWS Console, or run `aws sts get-caller-identity --query Account --output text`).

The wizard asks a series of questions. Answer them exactly as shown:

| Prompt | Answer |
|--------|--------|
| Stack Name [sam-app] | `music-subscription-lambda` |
| AWS Region [us-east-1] | Press **Enter** |
| Parameter LabRoleArn | *(paste your full LabRole ARN)* |
| Confirm changes before deploy [Y/n] | `y` |
| Allow SAM CLI IAM role creation [Y/n] | `n` |
| Disable rollback [y/N] | `n` |
| `MusicSubscriptionFunction` may not have authorization defined, Is this okay? | `y` *(repeat for each route — approximately 11 prompts)* |
| Save arguments to configuration file [Y/n] | `y` |
| SAM configuration file [samconfig.toml] | Press **Enter** |
| SAM configuration environment [default] | Press **Enter** |

SAM prints a changeset preview listing all resources to create. When asked
`Deploy this changeset? [y/N]` type `y`.

Deployment takes approximately 1–3 minutes. When done you will see:

```
Successfully created/updated stack - music-subscription-lambda in us-east-1
```

### Step 2.4 — Copy your API URL from the Outputs table

Immediately after deployment SAM prints:

```
------------------------------------------------------------------------------------
Outputs
------------------------------------------------------------------------------------
Key         ApiBaseUrl
Description Live API Gateway base URL — paste this into frontend/config.js
Value       https://nsf6ua05d6.execute-api.us-east-1.amazonaws.com/prod
------------------------------------------------------------------------------------
```

Copy the `Value`. You can also retrieve it later:

```bash
aws cloudformation describe-stacks \
  --stack-name music-subscription-lambda \
  --query "Stacks[0].Outputs[?OutputKey=='ApiBaseUrl'].OutputValue" \
  --output text
```

### Step 2.5 — Update the frontend config

Open `frontend/config.js` and set your URL:

```javascript
const API_BASE_URL = "https://nsf6ua05d6.execute-api.us-east-1.amazonaws.com/prod";
```

### Step 2.6 — Smoke test the live API

**Linux / Mac:**

```bash
export API="https://nsf6ua05d6.execute-api.us-east-1.amazonaws.com/prod"

# Health check
curl $API/

# Login
curl -X POST $API/login \
  -H "Content-Type: application/json" \
  -d '{"email":"s1234567+0@student.rmit.edu.au","password":"012345"}'

# Song query by artist
curl "$API/songs?artist=Taylor+Swift"
```

**Windows PowerShell:**

```powershell
$API = "https://nsf6ua05d6.execute-api.us-east-1.amazonaws.com/prod"

# Health check
Invoke-RestMethod -Uri "$API/"

# Login
Invoke-RestMethod -Method POST -Uri "$API/login" `
  -ContentType "application/json" `
  -Body '{"email":"s1234567+0@student.rmit.edu.au","password":"012345"}'

# Song query
Invoke-RestMethod -Uri "$API/songs?artist=Taylor Swift"
```

### Step 2.7 — Subsequent deploys (after code changes)

After the first deployment, SAM saves your settings to `samconfig.toml`. All
future deploys are a single command:

```bash
sam build --use-container && sam deploy
```

### Tear down Lambda stack

```bash
sam delete --stack-name music-subscription-lambda
```

Removes the API Gateway, Lambda function, and CloudFormation stack.
DynamoDB tables and S3 buckets are **not** deleted.

---

## Part 3 — ECS Fargate Backend

> ✅ The ECS code (`ecs_backend/`) is complete with no bugs.
>
> ⚠️ The most common failure: the ECS task IAM role missing DynamoDB/S3
> permissions. Follow Step 3.2 before anything else.

### Step 3.1 — Create an ECR repository

```bash
aws ecr create-repository \
  --repository-name music-subscription-api \
  --region us-east-1
```

From the output, note the `repositoryUri`:

```
123456789012.dkr.ecr.us-east-1.amazonaws.com/music-subscription-api
```

Store it for reuse:

```bash
# Linux/Mac
export ECR_URI="123456789012.dkr.ecr.us-east-1.amazonaws.com/music-subscription-api"

# Windows PowerShell
$ECR_URI = "123456789012.dkr.ecr.us-east-1.amazonaws.com/music-subscription-api"
```

### Step 3.2 — Attach DynamoDB and S3 permissions to LabRole

> **Do this before launching any tasks.** If you skip it, all API requests
> will return 403 from DynamoDB even though the container starts fine.

1. Go to **IAM → Roles → LabRole**
2. Click **Add permissions → Attach policies**
3. Search for and select **`AmazonDynamoDBFullAccess`** — tick the checkbox
4. Search for and select **`AmazonS3ReadOnlyAccess`** — tick the checkbox
5. Click **Add permissions**

Verify under **LabRole → Permissions** that both policies now appear.

### Step 3.3 — Build and push the Docker image

```bash
cd ecs_backend

# Authenticate Docker to your ECR registry
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin \
  123456789012.dkr.ecr.us-east-1.amazonaws.com

# Build the image
docker build -t music-subscription-api .

# Tag it for ECR
docker tag music-subscription-api:latest $ECR_URI:latest

# Push to ECR
docker push $ECR_URI:latest
```

Verify the push:

```bash
aws ecr list-images --repository-name music-subscription-api
```

You should see one image tagged `latest`.

### Step 3.4 — Create ECS cluster and log group

```bash
aws ecs create-cluster --cluster-name music-app-cluster

aws logs create-log-group --log-group-name /ecs/music-subscription
```

### Step 3.5 — Register the task definition

Create `task-def.json` (replace both `<YOUR_ACCOUNT_ID>` placeholders and the
ECR URI):

```json
{
  "family": "music-subscription-task",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "256",
  "memory": "512",
  "executionRoleArn": "arn:aws:iam::<YOUR_ACCOUNT_ID>:role/LabRole",
  "taskRoleArn": "arn:aws:iam::<YOUR_ACCOUNT_ID>:role/LabRole",
  "containerDefinitions": [
    {
      "name": "music-api",
      "image": "123456789012.dkr.ecr.us-east-1.amazonaws.com/music-subscription-api:latest",
      "portMappings": [
        { "containerPort": 80, "protocol": "tcp" }
      ],
      "essential": true,
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/music-subscription",
          "awslogs-region": "us-east-1",
          "awslogs-stream-prefix": "ecs"
        }
      }
    }
  ]
}
```

Register it:

```bash
aws ecs register-task-definition --cli-input-json file://task-def.json
```

### Step 3.6 — Get your default VPC and subnet

```bash
# Get default VPC ID
VPC_ID=$(aws ec2 describe-vpcs \
  --filters Name=isDefault,Values=true \
  --query "Vpcs[0].VpcId" --output text)
echo "VPC: $VPC_ID"

# Get a public subnet in that VPC
SUBNET_ID=$(aws ec2 describe-subnets \
  --filters "Name=vpc-id,Values=$VPC_ID" "Name=defaultForAz,Values=true" \
  --query "Subnets[0].SubnetId" --output text)
echo "Subnet: $SUBNET_ID"
```

### Step 3.7 — Create a security group and allow HTTP

```bash
SG_ID=$(aws ec2 create-security-group \
  --group-name music-api-sg \
  --description "Allow HTTP inbound for music API" \
  --vpc-id $VPC_ID \
  --query "GroupId" --output text)
echo "Security Group: $SG_ID"

aws ec2 authorize-security-group-ingress \
  --group-id $SG_ID \
  --protocol tcp \
  --port 80 \
  --cidr 0.0.0.0/0
```

### Step 3.8 — Launch the ECS service

```bash
aws ecs create-service \
  --cluster music-app-cluster \
  --service-name music-api-service \
  --task-definition music-subscription-task \
  --desired-count 1 \
  --launch-type FARGATE \
  --network-configuration \
    "awsvpcConfiguration={subnets=[$SUBNET_ID],securityGroups=[$SG_ID],assignPublicIp=ENABLED}"
```

Wait for the service to reach a steady state (up to 5 minutes):

```bash
aws ecs wait services-stable \
  --cluster music-app-cluster \
  --services music-api-service

echo "Service is running."
```

### Step 3.9 — Get the container's public IP

```bash
# Get task ARN
TASK_ARN=$(aws ecs list-tasks \
  --cluster music-app-cluster \
  --service-name music-api-service \
  --query "taskArns[0]" --output text)

# Get the ENI (network interface) attached to the task
ENI_ID=$(aws ecs describe-tasks \
  --cluster music-app-cluster \
  --tasks $TASK_ARN \
  --query "tasks[0].attachments[0].details[?name=='networkInterfaceId'].value" \
  --output text)

# Get the public IP of that ENI
PUBLIC_IP=$(aws ec2 describe-network-interfaces \
  --network-interface-ids $ENI_ID \
  --query "NetworkInterfaces[0].Association.PublicIp" \
  --output text)

echo "ECS Public IP: $PUBLIC_IP"
```

### Step 3.10 — Update the frontend config and smoke test

Open `frontend/config.js`:

```javascript
const API_BASE_URL = "http://<your-ecs-public-ip>";
```

Smoke test:

```bash
curl http://$PUBLIC_IP/
curl -X POST http://$PUBLIC_IP/login \
  -H "Content-Type: application/json" \
  -d '{"email":"s1234567+0@student.rmit.edu.au","password":"012345"}'
```

---

## Part 4 — Frontend Deployment

### Option A — S3 Static Website Hosting (Recommended)

Before uploading, confirm `frontend/config.js` has the correct `API_BASE_URL`.

```bash
# Create a dedicated frontend bucket (different from the images bucket)
aws s3api create-bucket \
  --bucket sonata-frontend-<your-student-id> \
  --region us-east-1

# Enable static website hosting
aws s3 website s3://sonata-frontend-<your-student-id>/ \
  --index-document login.html \
  --error-document login.html

# Disable public access block
aws s3api put-public-access-block \
  --bucket sonata-frontend-<your-student-id> \
  --public-access-block-configuration \
  "BlockPublicAcls=false,IgnorePublicAcls=false,BlockPublicPolicy=false,RestrictPublicBuckets=false"
```

Create `frontend-policy.json`:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": "*",
      "Action": "s3:GetObject",
      "Resource": "arn:aws:s3:::sonata-frontend-<your-student-id>/*"
    }
  ]
}
```

Apply policy and upload:

```bash
aws s3api put-bucket-policy \
  --bucket sonata-frontend-<your-student-id> \
  --policy file://frontend-policy.json

aws s3 sync frontend/ s3://sonata-frontend-<your-student-id>/
```

Your app is live at:

```
http://sonata-frontend-<your-student-id>.s3-website-us-east-1.amazonaws.com/login.html
```

### Option B — Open locally (quick testing only)

Open `frontend/login.html` directly in your browser. Since `config.js` points
to a live HTTPS URL, the frontend connects to your real deployed backend
without needing a local web server.

---

## Part 5 — End-to-End Verification

### Automated DynamoDB test

```bash
cd data_setup
python verify_system.py
```

All 5 tests passing confirms your tables, credentials, and data setup are working:

```
--- TEST 1: LOGIN ---
Login user found: GroupUser0

--- TEST 2: MUSIC QUERY (Artist) ---
Found 7 songs for Taylor Swift
- Bad Blood (2014)
- Delicate (2017)
- I Knew You Were Trouble (2012)

--- TEST 3: ADD SUBSCRIPTION ---
Subscribed to: 1904

--- TEST 4: VIEW SUBSCRIPTIONS ---
Total subscriptions: 1
- 1904 (The Tallest Man on Earth)

--- TEST 5: REMOVE SUBSCRIPTION ---
Removed: 1904

--- TEST 4: VIEW SUBSCRIPTIONS ---
Total subscriptions: 0
```

### Manual browser test

1. Open the frontend URL (or `login.html` locally)
2. Log in with `s1234567+0@student.rmit.edu.au` / `012345`
3. You should land on `index.html` with My Library empty
4. Search for `Taylor Swift` in the Artist field — expect 7 song cards with images
5. Click **+ Subscribe** on any song — it should appear in My Library immediately
6. Click **✕ Remove** — it should disappear from My Library

---

## API Reference

Base URL: `https://<api-id>.execute-api.us-east-1.amazonaws.com/prod`

The `music_id` composite key format used for subscriptions:
`{artist}#{title}#{year}#{album}`

### GET `/`
Health check.
**Response 200:** `{"message": "AWS Music Subscription Lambda Backend is running"}`

### POST `/login`
**Body:** `{"email": "...", "password": "..."}`
**200:** `{"success": true, "user_name": "GroupUser0", "email": "..."}`
**401:** `{"success": false, "message": "email or password is invalid"}`

### POST `/register`
**Body:** `{"email": "...", "user_name": "...", "password": "..."}`
**201:** `{"success": true, "message": "registration successful"}`
**409:** `{"success": false, "message": "The email already exists"}`

### GET `/songs`
At least one query param required: `title`, `artist`, `year`, `album`.
Multiple params are combined with AND logic.
```
GET /songs?artist=Taylor+Swift
GET /songs?artist=Taylor+Swift&album=Fearless
GET /songs?title=Hotel+California
GET /songs?year=1977
```
**200 (found):** `{"success": true, "songs": [{"title": "...", "artist": "...", "year": "...", "album": "...", "image_url": "...", "image_s3_key": "..."}, ...]}`
**200 (no results):** `{"success": true, "message": "No result is retrieved. Please query again", "songs": []}`

### GET `/subscriptions?email=<email>`
**200:** `{"success": true, "subscriptions": [...]}`

### POST `/subscriptions`
**Body:** `{"email": "...", "title": "...", "artist": "...", "year": "...", "album": "...", "image_s3_key": "..."}`
**201:** `{"success": true, "message": "subscription added successfully"}`

### DELETE `/subscriptions`
**Body:** `{"email": "...", "music_id": "Taylor Swift#Love Story#2008#Fearless"}`
**200:** `{"success": true, "message": "subscription removed successfully"}`

---

## Troubleshooting

### `NoCredentialsError` or `ExpiredTokenException`
Your AWS Academy session has expired. Refresh credentials from the AWS Academy
lab panel and paste them into `~/.aws/credentials`. See [AWS Credentials](#aws-credentials).

### `ResourceNotFoundException: Requested resource not found`
The DynamoDB table does not exist yet. Run `python create_tables.py` first. If
tables exist but the error persists, confirm `AWS_REGION` in `config.py` is
`us-east-1` and matches your actual deployment region.

### Images not loading in the browser
Work through this checklist in order:
1. Confirm `upload_artist_images.py` completed without errors
2. Confirm `update_music_s3_keys.py` ran **after** the upload script — if you
   skip this step, `image_s3_key` stays empty in DynamoDB and no URL is generated
3. In the AWS Console go to **S3 → your bucket → Permissions** and confirm
   "Block all public access" shows **Off**
4. Confirm the bucket policy is applied (check **Permissions → Bucket policy**)
5. Manually test one image in your browser:
   `https://music-app-images-kingston-4156256-2026.s3.amazonaws.com/artists/TaylorSwift.jpg`

### Lambda returns `{"message": "Internal Server Error"}`
This is API Gateway's generic wrapper for an unhandled Lambda exception.

1. Go to **CloudWatch → Log groups → /aws/lambda/music-subscription-handler**
2. Click the most recent log stream
3. Find the line beginning with `[ERROR]` — it shows the full Python traceback

Common causes and fixes:
- Lambda execution role missing DynamoDB permissions → attach `AmazonDynamoDBFullAccess` to LabRole
- Table name mismatch → confirm `LOGIN_TABLE`, `MUSIC_TABLE`, `SUBSCRIPTIONS_TABLE` in `lambda_function.py` match what `create_tables.py` created
- AWS session token expired in the Lambda environment → run `sam build --use-container && sam deploy` again

### `AccessDeniedException` on all ECS API calls
The ECS task role does not have DynamoDB or S3 permissions. Go to
**IAM → Roles → LabRole → Permissions** and attach `AmazonDynamoDBFullAccess`
and `AmazonS3ReadOnlyAccess`. Then force a new task deployment:

```bash
aws ecs update-service \
  --cluster music-app-cluster \
  --service music-api-service \
  --force-new-deployment
```

### ECS task keeps restarting / stays in PENDING indefinitely
Check CloudWatch Logs at `/ecs/music-subscription` for the crash reason. Common causes:
- ECR image URI in `task-def.json` has a typo — verify account ID, region, and repo name
- Security group not allowing inbound TCP on port 80
- Subnet is private (no internet gateway) — the task needs a public IP to pull the image from ECR

### `sam build` fails with `Error: Docker is not reachable`
Docker Desktop is not running. Open it from your Applications or Start menu,
wait for the whale icon to stop animating, then retry.

### `sam deploy` fails with `No changes to deploy`
SAM detected no difference from the previous deployment. If you made changes:

```bash
sam build --use-container && sam deploy --force-upload
```

### CORS error in browser console
**Lambda:** The fixed `lambda_function.py` returns CORS headers on every response
including OPTIONS. If CORS errors still appear, the request is likely hitting a
route that doesn't exist (API Gateway returns its own 403/404 without CORS
headers). Verify the resource and method exist in API Gateway and that you
**redeployed the API** after creating them (Actions → Deploy API).

**ECS:** `flask_cors` is applied globally via `CORS(app)`. If CORS errors appear,
the container is likely crashing — check the CloudWatch Logs.

### Frontend login immediately redirects back to login page
`sessionStorage.getItem('userEmail')` in `app.js` is null, meaning the login
request failed silently. Open **Browser DevTools → Network tab**, attempt
login, and inspect the actual `/login` response — the error message will be in
the response body.

---

## AWS Resources Summary

| Resource | Name / Value |
|----------|-------------|
| DynamoDB table | `login` |
| DynamoDB table | `music` |
| DynamoDB table | `subscriptions` |
| S3 bucket — artist images | `music-app-images-kingston-4156256-2026` |
| S3 bucket — frontend | `sonata-frontend-<your-student-id>` |
| Lambda function | `music-subscription-handler` |
| API Gateway REST API | `music-subscription-api` (stage: `prod`) |
| CloudFormation stack | `music-subscription-lambda` |
| ECR repository | `music-subscription-api` |
| ECS cluster | `music-app-cluster` |
| ECS service | `music-api-service` |
| CloudWatch log group | `/ecs/music-subscription` |
| IAM role | `LabRole` (used for Lambda execution + ECS task) |
| AWS region | `us-east-1` |
