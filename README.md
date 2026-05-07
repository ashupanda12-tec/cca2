# Cloud-A2-146 — Sonata Music Subscription App

A cloud-native music subscription web application built on AWS as part of Cloud Computing Assignment 2. The app allows users to register, log in, search songs, and manage a personal subscription library.

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Prerequisites](#prerequisites)
3. [Project Structure](#project-structure)
4. [Step 1 — AWS Environment Setup](#step-1--aws-environment-setup)
5. [Step 2 — DynamoDB Tables](#step-2--dynamodb-tables)
6. [Step 3 — S3 Bucket & Artist Images](#step-3--s3-bucket--artist-images)
7. [Step 4 — Seed the Database](#step-4--seed-the-database)
8. [Step 5A — Deploy Backend via AWS Lambda + API Gateway](#step-5a--deploy-backend-via-aws-lambda--api-gateway)
9. [Step 5B — Deploy Backend via AWS ECS (Fargate)](#step-5b--deploy-backend-via-aws-ecs-fargate)
10. [Step 6 — Deploy the Frontend](#step-6--deploy-the-frontend)
11. [Step 7 — Verify the System](#step-7--verify-the-system)
12. [API Reference](#api-reference)
13. [Troubleshooting](#troubleshooting)

---

## Architecture Overview

```
Browser (Frontend)
      │
      ▼
Amazon S3 (Static Website Hosting)
      │
      ▼  REST API calls
┌─────────────────────────────────────┐
│  Option A: API Gateway → Lambda     │
│  Option B: ALB → ECS Fargate        │
└─────────────────────────────────────┘
      │
      ▼
 DynamoDB Tables          S3 Bucket
 ┌────────────┐           (Artist Images)
 │  login     │
 │  music     │
 │subscriptions│
 └────────────┘
```

- **Frontend** — Static HTML/CSS/JS (Sonata UI) hosted on S3
- **Backend Option A (Recommended)** — Python Flask deployed as an AWS Lambda function behind API Gateway
- **Backend Option B** — Python Flask in a Docker container deployed on ECS Fargate
- **Database** — Amazon DynamoDB (3 tables)
- **Media Storage** — Amazon S3 (artist images)

---

## Prerequisites

### Local Machine Requirements

| Tool | Version | Purpose |
|------|---------|---------|
| Python | 3.10 or higher | Running data setup scripts |
| pip | Latest | Installing Python packages |
| AWS CLI | v2 | Interacting with AWS from terminal |
| Docker | Latest | Required for ECS deployment only |
| Git | Any | Cloning the repository |

### Install Python dependencies for data setup scripts

```bash
cd data_setup
pip install boto3 requests
```

### AWS Account Requirements

- An active AWS Academy or standard AWS account
- IAM permissions for: **DynamoDB**, **S3**, **Lambda**, **API Gateway**, **ECS**, **ECR**, **IAM**, **CloudWatch**
- AWS CLI configured with your credentials (see Step 1)

---

## Project Structure

```
Cloud-A2-146/
├── data_setup/                  # One-time setup scripts (run locally)
│   ├── config.py                # Shared config: region, table names, S3 bucket
│   ├── create_tables.py         # Creates the 3 DynamoDB tables
│   ├── seed_login_table.py      # Seeds 10 default login users
│   ├── load_music_table.py      # Loads all songs into DynamoDB
│   ├── upload_artist_images.py  # Downloads & uploads artist images to S3
│   ├── update_music_s3_keys.py  # Writes S3 image keys back to music table
│   ├── verify_system.py         # End-to-end verification test
│   └── 2026a2_songs.json        # Song dataset (137 songs)
│
├── lambda_backend/
│   └── lambda_function.py       # ✅ Complete — Lambda handler (all routes)
│
├── ecs_backend/                 # ✅ Complete — Dockerised Flask app
│   ├── app.py
│   ├── config.py
│   ├── requirements.txt
│   └── Dockerfile
│
├── backend_flask/               # ⚠️  Incomplete — local EC2 Flask (not for submission)
│   ├── app.py
│   ├── config.py
│   └── requirements.txt
│
└── frontend/                    # Static web UI
    ├── login.html
    ├── register.html
    ├── index.html               # Main app page
    ├── login.js
    ├── register.js
    ├── app.js
    └── config.js                # ← Update API_BASE_URL here
```

---

## Step 1 — AWS Environment Setup

### 1.1 Configure AWS CLI

```bash
aws configure
```

Enter the following when prompted:

```
AWS Access Key ID:     <your key>
AWS Secret Access Key: <your secret>
Default region name:   us-east-1
Default output format: json
```

> **AWS Academy users:** Copy credentials from the Vocareum "AWS Details" panel. Also export `AWS_SESSION_TOKEN`:
> ```bash
> export AWS_SESSION_TOKEN=<your_session_token>
> ```

### 1.2 Verify CLI access

```bash
aws sts get-caller-identity
```

You should see your account ID and ARN. If you get an error, recheck your credentials.

---

## Step 2 — DynamoDB Tables

This script creates three tables: `login`, `music`, and `subscriptions`.

```bash
cd data_setup
python create_tables.py
```

Expected output:

```
Creating table 'login'...
Table 'login' is now active.

Creating table 'music'...
Table 'music' is now active.

Creating table 'subscriptions'...
Table 'subscriptions' is now active.

All required tables are ready.
```

> If you see "already exists. Skipping creation." the tables are already there — this is fine.

**Verify in AWS Console:** Go to DynamoDB → Tables and confirm all 3 tables appear with status **Active**.

---

## Step 3 — S3 Bucket & Artist Images

### 3.1 Create the S3 Bucket

The bucket name is already set in `data_setup/config.py`:

```python
S3_BUCKET_NAME = "music-app-images-kingston-4156256-2026"
```

Create it via AWS CLI:

```bash
aws s3api create-bucket \
  --bucket music-app-images-kingston-4156256-2026 \
  --region us-east-1
```

### 3.2 Enable Public Access

```bash
aws s3api put-public-access-block \
  --bucket music-app-images-kingston-4156256-2026 \
  --public-access-block-configuration \
  "BlockPublicAcls=false,IgnorePublicAcls=false,BlockPublicPolicy=false,RestrictPublicBuckets=false"
```

### 3.3 Apply a Public Read Bucket Policy

Create a file called `bucket-policy.json`:

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

Apply it:

```bash
aws s3api put-bucket-policy \
  --bucket music-app-images-kingston-4156256-2026 \
  --policy file://bucket-policy.json
```

### 3.4 Upload Artist Images

```bash
cd data_setup
python upload_artist_images.py
```

This downloads each artist's image from the source URLs and uploads them to `s3://music-app-images-kingston-4156256-2026/artists/`.

---

## Step 4 — Seed the Database

Run these scripts **in order**:

### 4.1 Seed login users

```bash
cd data_setup
python seed_login_table.py
```

This inserts 10 test accounts. Credentials follow the pattern:

| Email | Password |
|-------|----------|
| s1234567+0@student.rmit.edu.au | 012345 |
| s1234567+1@student.rmit.edu.au | 123456 |
| ... | ... |
| s1234567+9@student.rmit.edu.au | 901234 |

> Update `GROUP_BASE_STUDENT_ID` and `GROUP_BASE_NAME` in `data_setup/config.py` to match your actual student ID before running.

### 4.2 Load the music table

```bash
python load_music_table.py
```

Loads all 137 songs from `2026a2_songs.json` into DynamoDB.

### 4.3 Write S3 image keys to music records

```bash
python update_music_s3_keys.py
```

This writes the `image_s3_key` field (e.g. `artists/TaylorSwift.jpg`) back to every song record in DynamoDB so the backend can serve full image URLs.

---

## Step 5A — Deploy Backend via AWS Lambda + API Gateway

> ✅ This is the **recommended and complete** deployment path.

### 5.1 Create the Lambda Function

In the AWS Console:

1. Go to **Lambda → Create function**
2. Choose **Author from scratch**
3. Settings:
   - **Function name:** `music-subscription-api`
   - **Runtime:** Python 3.10
   - **Architecture:** x86_64
4. Under **Permissions**, choose or create a role with:
   - `AmazonDynamoDBFullAccess`
   - `AmazonS3ReadOnlyAccess`
   - `AWSLambdaBasicExecutionRole`
5. Click **Create function**

### 5.2 Upload the Lambda Code

From the Lambda console:

1. Click **Code** tab → **Upload from** → **.zip file**
2. Create the zip locally first:

```bash
cd lambda_backend
zip lambda_function.zip lambda_function.py
```

3. Upload `lambda_function.zip`
4. Set **Handler** to: `lambda_function.lambda_handler`

### 5.3 Configure Environment (optional)

The Lambda function uses hardcoded config. No environment variables needed unless you customise the bucket name or table names.

### 5.4 Set Timeout and Memory

In **Configuration → General configuration**:
- **Timeout:** 30 seconds
- **Memory:** 256 MB

### 5.5 Create API Gateway

1. Go to **API Gateway → Create API**
2. Choose **REST API → Build**
3. Settings:
   - **API name:** `music-subscription-gateway`
   - **Endpoint type:** Regional
4. Click **Create API**

### 5.6 Create Resources and Methods

Create the following routes. For **each route**, the integration type is **Lambda Function** pointing to `music-subscription-api` with **Lambda Proxy integration** enabled.

| Resource | Method |
|----------|--------|
| `/login` | POST |
| `/register` | POST |
| `/songs` | GET |
| `/subscriptions` | GET |
| `/subscriptions` | POST |
| `/subscriptions` | DELETE |

For each resource, also create an **OPTIONS** method (for CORS):
- Integration type: **Mock**
- Method Response: 200
- Integration Response headers: `Access-Control-Allow-Headers`, `Access-Control-Allow-Methods`, `Access-Control-Allow-Origin` all set to `'*'`

### 5.7 Enable CORS

For each resource, click **Actions → Enable CORS** and confirm. The Lambda function already returns CORS headers so this is a safety net.

### 5.8 Deploy the API

1. Click **Actions → Deploy API**
2. **Deployment stage:** `prod` (create new)
3. Click **Deploy**

Copy the **Invoke URL** — it looks like:

```
https://nsf6ua05d6.execute-api.us-east-1.amazonaws.com/prod
```

### 5.9 Update the Frontend Config

Open `frontend/config.js` and set:

```javascript
const API_BASE_URL = "https://<your-api-id>.execute-api.us-east-1.amazonaws.com/prod";
```

---

## Step 5B — Deploy Backend via AWS ECS (Fargate)

> ✅ This is the **alternative complete** deployment path using Docker containers.

### 5B.1 Create an ECR Repository

```bash
aws ecr create-repository \
  --repository-name music-subscription-api \
  --region us-east-1
```

Note the `repositoryUri` from the output, e.g.:
`123456789012.dkr.ecr.us-east-1.amazonaws.com/music-subscription-api`

### 5B.2 Build and Push the Docker Image

```bash
cd ecs_backend

# Authenticate Docker to ECR
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin \
  123456789012.dkr.ecr.us-east-1.amazonaws.com

# Build the image
docker build -t music-subscription-api .

# Tag the image
docker tag music-subscription-api:latest \
  123456789012.dkr.ecr.us-east-1.amazonaws.com/music-subscription-api:latest

# Push to ECR
docker push \
  123456789012.dkr.ecr.us-east-1.amazonaws.com/music-subscription-api:latest
```

### 5B.3 Create an ECS Cluster

```bash
aws ecs create-cluster --cluster-name music-app-cluster
```

### 5B.4 Create a Task Definition

Create a file `task-def.json`:

```json
{
  "family": "music-subscription-task",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "256",
  "memory": "512",
  "executionRoleArn": "arn:aws:iam::<your-account-id>:role/ecsTaskExecutionRole",
  "taskRoleArn": "arn:aws:iam::<your-account-id>:role/ecsTaskExecutionRole",
  "containerDefinitions": [
    {
      "name": "music-api",
      "image": "123456789012.dkr.ecr.us-east-1.amazonaws.com/music-subscription-api:latest",
      "portMappings": [
        {
          "containerPort": 80,
          "protocol": "tcp"
        }
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

Register the task definition:

```bash
aws ecs register-task-definition --cli-input-json file://task-def.json
```

> Make sure `ecsTaskExecutionRole` has `AmazonDynamoDBFullAccess` and `AmazonS3ReadOnlyAccess` attached.

### 5B.5 Create a Security Group

```bash
aws ec2 create-security-group \
  --group-name music-api-sg \
  --description "Music API security group"

# Allow inbound HTTP on port 80
aws ec2 authorize-security-group-ingress \
  --group-name music-api-sg \
  --protocol tcp --port 80 --cidr 0.0.0.0/0
```

Note the `GroupId` from the output (e.g. `sg-0abc123`).

### 5B.6 Run the ECS Service

```bash
aws ecs create-service \
  --cluster music-app-cluster \
  --service-name music-api-service \
  --task-definition music-subscription-task \
  --desired-count 1 \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[subnet-xxxxxxxx],securityGroups=[sg-0abc123],assignPublicIp=ENABLED}"
```

> Replace `subnet-xxxxxxxx` with a public subnet ID from your default VPC. Find it in the EC2 Console → Subnets.

### 5B.7 Get the Public IP

```bash
# Get the task ARN
aws ecs list-tasks --cluster music-app-cluster --service-name music-api-service

# Describe the task to get ENI
aws ecs describe-tasks \
  --cluster music-app-cluster \
  --tasks <task-arn>
```

Look for `networkInterfaceId` in the output, then:

```bash
aws ec2 describe-network-interfaces \
  --network-interface-ids <eni-id> \
  --query 'NetworkInterfaces[0].Association.PublicIp'
```

Update `frontend/config.js`:

```javascript
const API_BASE_URL = "http://<ecs-public-ip>";
```

---

## Step 6 — Deploy the Frontend

### Option A — S3 Static Website Hosting (Recommended)

#### 6.1 Create a frontend S3 bucket

```bash
aws s3api create-bucket \
  --bucket sonata-frontend-<your-student-id> \
  --region us-east-1
```

#### 6.2 Enable static website hosting

```bash
aws s3 website s3://sonata-frontend-<your-student-id>/ \
  --index-document login.html \
  --error-document login.html
```

#### 6.3 Make it public

Apply the same public-read bucket policy as in Step 3.3 (update the bucket name accordingly).

#### 6.4 Upload frontend files

Make sure `frontend/config.js` has the correct `API_BASE_URL` first, then:

```bash
aws s3 sync frontend/ s3://sonata-frontend-<your-student-id>/
```

#### 6.5 Access the app

Your app is live at:

```
http://sonata-frontend-<your-student-id>.s3-website-us-east-1.amazonaws.com/login.html
```

### Option B — Open Locally

Simply open `frontend/login.html` in a browser. Since `config.js` points to a deployed API URL, this works without any server.

---

## Step 7 — Verify the System

Run the automated verification script to confirm all components are working:

```bash
cd data_setup
python verify_system.py
```

Expected output:

```
--- TEST 1: LOGIN ---
Login user found: GroupUser0

--- TEST 2: MUSIC QUERY (Artist) ---
Found 7 songs for Taylor Swift
- Bad Blood (2014)
- Delicate (2017)
- ...

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

All 5 tests passing means your DynamoDB tables and credentials are fully operational.

---

## API Reference

Base URL: `https://<api-id>.execute-api.us-east-1.amazonaws.com/prod`

### POST `/login`

```json
{ "email": "s1234567+0@student.rmit.edu.au", "password": "012345" }
```

**Success 200:** `{ "success": true, "user_name": "GroupUser0", "email": "..." }`
**Failure 401:** `{ "success": false, "message": "email or password is invalid" }`

---

### POST `/register`

```json
{ "email": "newuser@example.com", "user_name": "Alice", "password": "secret" }
```

**Success 201:** `{ "success": true, "message": "registration successful" }`
**Conflict 409:** `{ "success": false, "message": "The email already exists" }`

---

### GET `/songs`

Query parameters (at least one required): `title`, `artist`, `year`, `album`

```
GET /songs?artist=Taylor+Swift
GET /songs?title=Hotel+California&year=1977
```

**Success 200:** `{ "success": true, "songs": [ { "title": "...", "artist": "...", "image_url": "..." }, ... ] }`

---

### GET `/subscriptions?email=<email>`

Returns all subscriptions for a user.

---

### POST `/subscriptions`

```json
{
  "email": "user@example.com",
  "title": "Ho Hey",
  "artist": "The Lumineers",
  "year": "2012",
  "album": "The Lumineers",
  "image_s3_key": "artists/TheLumineers.jpg"
}
```

---

### DELETE `/subscriptions`

```json
{ "email": "user@example.com", "music_id": "The Lumineers#Ho Hey#2012#The Lumineers" }
```

---

## Troubleshooting

### `botocore.exceptions.NoCredentialsError`
Your AWS credentials are not configured. Re-run `aws configure` or re-export your session token if using AWS Academy.

### `ResourceNotFoundException` when running setup scripts
The DynamoDB tables don't exist yet. Run `python create_tables.py` first.

### Images not loading in the frontend
- Confirm `upload_artist_images.py` ran successfully
- Confirm `update_music_s3_keys.py` ran after that
- Verify the S3 bucket policy allows public reads (Step 3.3)

### API Gateway returns `{"message": "Internal Server Error"}`
- Open **CloudWatch → Log groups → /aws/lambda/music-subscription-api** to see the Python traceback
- Common cause: Lambda execution role is missing DynamoDB permissions

### ECS container keeps restarting
- Check CloudWatch Logs at `/ecs/music-subscription`
- Verify the task role has DynamoDB and S3 permissions
- Confirm the security group allows inbound TCP on port 80

### CORS errors in the browser console
- Confirm OPTIONS method exists for each API Gateway resource
- Confirm CORS was enabled (Actions → Enable CORS) and the API was **redeployed** after making changes

---

## Notes

- EC2 backend (`backend_flask/`) is **incomplete** and not used in this submission
- Lambda and ECS backends are functionally identical — both use the same DynamoDB tables and S3 bucket
- The `music_id` composite key format is: `{artist}#{title}#{year}#{album}`
- AWS Academy sessions expire after a few hours — re-export credentials and restart any Lambda/ECS deployments if things stop working
