# Cloud Computing A2 — Music Subscription Application

A cloud-based music subscription web application built on AWS using DynamoDB,
S3, EC2, API Gateway, and Lambda.

---

## Quick Start — Order of Operations

If you are setting this up from scratch, follow these steps in order:

1. [Install prerequisites](#prerequisites)
2. [Configure the three personal values](#before-you-start--required-configuration) (S3 bucket name, student ID)
3. [Set up AWS credentials](#aws-credentials)
4. [Run the infrastructure scripts](#part-1--aws-infrastructure-setup) (DynamoDB tables + S3 images)
5. Deploy a backend: [EC2](#part-2--ec2-backend) | [ECS](#part-3--ecs-fargate-backend) | [Lambda](#part-4--api-gateway--lambda-backend)

---

## Project Structure

```
Cloud_Computing_A2/
├── data/
│   ├── 2026a2_songs.json              # Source dataset (137 songs)
│   └── images/                        # Local artist image cache (auto-created by upload script)
├── scripts/
│   ├── create_login_table.py          # Create & populate the login DynamoDB table
│   ├── create_music_table.py          # Create the music DynamoDB table (GSI + LSI)
│   ├── create_subscriptions_table.py  # Create the subscriptions DynamoDB table
│   ├── load_music_data.py             # Load 137 songs into the music table
│   └── upload_images_to_s3.py         # Upload artist images to S3
├── backend/
│   ├── ec2/                           # Flask backend (EC2 deployment)
│   │   ├── app.py                     # Flask entry point
│   │   ├── config.py                  # AWS config constants
│   │   ├── requirements.txt           # Python dependencies
│   │   ├── setup.sh                   # One-shot EC2 setup script
│   │   ├── routes/
│   │   │   ├── auth.py                # POST /auth/login, /register, /logout
│   │   │   ├── music.py               # GET  /music/query
│   │   │   └── subscriptions.py       # GET/POST/DELETE /subscriptions
│   │   └── services/
│   │       ├── dynamo.py              # All DynamoDB operations
│   │       └── s3.py                  # S3 pre-signed URL generation
│   ├── ecs/                           # Flask backend (ECS Fargate deployment)
│   │   ├── Dockerfile                 # Container image definition
│   │   ├── docker-compose.yml         # Local testing with real AWS credentials
│   │   ├── app.py                     # Flask entry point (identical to EC2)
│   │   ├── config.py                  # AWS config constants
│   │   ├── requirements.txt           # Python dependencies
│   │   ├── routes/                    # Same routes as EC2
│   │   ├── services/                  # Same DynamoDB/S3 services as EC2
│   │   └── deploy/
│   │       ├── task-definition.json   # ECS Fargate task definition template
│   │       └── setup.sh               # Full AWS CLI deployment script
│   └── lambda/                        # Serverless backend (API Gateway + Lambda)
│       ├── template.yaml              # AWS SAM template (API GW + Lambda definitions)
│       ├── config.py                  # Same constants as EC2
│       ├── requirements.txt           # Python dependencies for packaging
│       ├── test_local.py              # Direct handler tests (no Docker/SAM needed)
│       ├── handlers/
│       │   ├── auth.py                # login_handler, register_handler, logout_handler
│       │   ├── music.py               # query_handler
│       │   └── subscriptions.py       # list_handler, subscribe_handler, unsubscribe_handler
│       └── services/
│           ├── dynamo.py              # All DynamoDB operations (identical to EC2)
│           └── s3.py                  # S3 pre-signed URL generation (identical to EC2)
└── requirements.txt                   # Dependencies for infrastructure scripts
```

---

## Prerequisites

Install the following before starting:

- **Python 3.10+** — [python.org](https://www.python.org/downloads/)
- **AWS SAM CLI** — required for the Lambda backend: [install guide](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html)
- **Docker Desktop** — required for ECS deployment and for `sam local start-api` (local Lambda simulation): [docker.com](https://www.docker.com/products/docker-desktop/)
- **Git** — to clone the repo

Then install the Python dependencies for the infrastructure scripts:

```powershell
pip install -r requirements.txt
```

---

## AWS Credentials

All scripts and backends authenticate with AWS using credentials from
`~/.aws/credentials`. AWS Academy credentials expire when your lab session
ends, so you need to refresh them at the start of every session.

**How to set up / refresh credentials:**

1. Open your AWS Academy Lab and start a session
2. Click **AWS Details** → **AWS CLI**
3. Click **Copy** on the credentials block
4. Paste it into `C:\Users\<you>\.aws\credentials` (Windows) or `~/.aws/credentials` (Mac/Linux), replacing the existing content

The file should look like:
```
[default]
aws_access_key_id = ASIA...
aws_secret_access_key = ...
aws_session_token = ...
```

> **Important:** These credentials expire after a few hours. If you get
> `ExpiredTokenException` errors, go back to AWS Academy and refresh them.

---

## Before You Start — Required Configuration

Three values in the codebase are specific to each developer and **must be
updated before running any scripts or deploying any backend**.

### 1. S3 bucket name

S3 bucket names must be globally unique across all of AWS. Choose your own
(e.g. `sXXXXXXX-music-artist-images` using your student number) and update it
in all three of these files:

| File | What to update |
|------|----------------|
| `scripts/upload_images_to_s3.py` | `BUCKET_NAME = "your-bucket-name-here"` |
| `backend/ec2/config.py` | default value in `os.environ.get("S3_BUCKET", "your-bucket-name-here")` |
| `backend/lambda/config.py` | default value in `os.environ.get("S3_BUCKET", "your-bucket-name-here")` |

All three must use the **same bucket name**.

> Alternatively, set the `S3_BUCKET` environment variable in your shell and
> the backends will pick it up automatically without editing the files.

### 2. Login table seed users

`scripts/create_login_table.py` generates 10 seed users based on your student
details. Open the file and update these three constants before running it:

```python
STUDENT_ID = "sXXXXXXX"   # your RMIT student number, e.g. "s1234567"
FIRST_NAME = "FirstName"   # your first name
LAST_NAME  = "LastName"    # your last name
```

This produces 10 seed users: `sXXXXXXX0@student.rmit.edu.au` through
`sXXXXXXX9@student.rmit.edu.au` with passwords `012345` through `901234`.
Replace `sXXXXXXX0` with your actual first seed email in all test commands.

### 3. Lambda test script seed email

Update the seed email in `backend/lambda/test_local.py` to match:

```python
_SEED_EMAIL = "sXXXXXXX0@student.rmit.edu.au"  # your first seed user
```

---

## Part 1 — AWS Infrastructure Setup

Run these five scripts once to provision DynamoDB tables and populate S3.
**Run them in order from the repo root.**

### 1. Create the login table

```powershell
python scripts/create_login_table.py
```

Creates a `login` table with 10 seed users. Partition key: `email`.

### 2. Create the music table

```powershell
python scripts/create_music_table.py
```

Creates a `music` table with the following key schema:

| Key / Index             | Partition Key | Sort Key      |
|-------------------------|---------------|---------------|
| Primary key             | `title`       | `artist#year` |
| GSI: `artist-index`     | `artist`      | `year`        |
| LSI: `title-year-index` | `title`       | `year`        |

### 3. Create the subscriptions table

```powershell
python scripts/create_subscriptions_table.py
```

Creates a `subscriptions` table. Partition key: `email`, sort key: `song_id`
(composite value `title#artist#year`).

### 4. Load music data

```powershell
python scripts/load_music_data.py
```

Loads all 137 songs from `data/2026a2_songs.json` into the `music` table.
Use `--dry-run` to preview without writing.

### 5. Upload artist images to S3

```powershell
python scripts/upload_images_to_s3.py
```

Downloads 71 unique artist images and uploads them to your S3 bucket.
Use `--dry-run` to preview. The bucket is created automatically if it doesn't
exist.

---

## Part 2 — EC2 Backend

### Local Development

Test the Flask backend locally against real AWS resources:

```powershell
cd backend\ec2
pip install -r requirements.txt
python app.py
```

The server starts at `http://localhost:5000`.

**Test endpoints (PowerShell):**

```powershell
# Health check
Invoke-RestMethod -Uri "http://localhost:5000/health"

# Login (replace with your seed email)
Invoke-RestMethod -Method POST -Uri "http://localhost:5000/auth/login" `
  -ContentType "application/json" `
  -Body '{"email":"sXXXXXXX0@student.rmit.edu.au","password":"012345"}'

# Register a new user
Invoke-RestMethod -Method POST -Uri "http://localhost:5000/auth/register" `
  -ContentType "application/json" `
  -Body '{"email":"newuser@test.com","user_name":"TestUser","password":"abc123"}'

# Query songs by artist
Invoke-RestMethod -Uri "http://localhost:5000/music/query?artist=Taylor Swift"

# Query by artist + album (AND logic)
Invoke-RestMethod -Uri "http://localhost:5000/music/query?artist=Taylor Swift&album=Fearless"

# Subscribe to a song
Invoke-RestMethod -Method POST -Uri "http://localhost:5000/subscriptions" `
  -ContentType "application/json" `
  -Body '{"email":"sXXXXXXX0@student.rmit.edu.au","title":"Love Story","artist":"Taylor Swift","year":"2008","album":"Fearless","image_url":"https://example.com/TaylorSwift.jpg"}'

# List subscriptions
Invoke-RestMethod -Uri "http://localhost:5000/subscriptions?email=sXXXXXXX0@student.rmit.edu.au"

# Remove a subscription
Invoke-RestMethod -Method DELETE -Uri "http://localhost:5000/subscriptions" `
  -ContentType "application/json" `
  -Body '{"email":"sXXXXXXX0@student.rmit.edu.au","title":"Love Story","artist":"Taylor Swift","year":"2008"}'
```

**Test endpoints (Linux/macOS):**

```bash
# Health check
curl http://localhost:5000/health

# Login
curl -X POST http://localhost:5000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"sXXXXXXX0@student.rmit.edu.au","password":"012345"}'

# Query songs by artist
curl "http://localhost:5000/music/query?artist=Taylor%20Swift"

# Query by artist + album
curl "http://localhost:5000/music/query?artist=Taylor%20Swift&album=Fearless"
```

---

### AWS Deployment (EC2)

#### 1. Launch an EC2 instance

| Setting               | Value                          |
|-----------------------|--------------------------------|
| AMI                   | Amazon Linux 2023              |
| Instance type         | t3.micro                       |
| Key pair              | vockey (AWS Academy default)   |
| IAM instance profile  | LabInstanceProfile             |
| Security group        | Allow HTTP (80) and SSH (22)   |

#### 2. Upload the code

```powershell
scp -i "C:\path\to\labsuser.pem" -r "C:\path\to\Cloud_Computing_A2" ec2-user@<EC2-IP>:~
```

#### 3. SSH in and run setup

```bash
ssh -i "C:\path\to\labsuser.pem" ec2-user@<EC2-IP>

chmod +x ~/Cloud_Computing_A2/backend/ec2/setup.sh
sudo ~/Cloud_Computing_A2/backend/ec2/setup.sh
```

The setup script installs Python 3.11, gunicorn, and nginx, creates a systemd
service, and starts everything. nginx listens on port 80 and reverse-proxies
to gunicorn on port 5000.

#### 4. Set the S3 bucket environment variable

The backend reads the bucket name from the `S3_BUCKET` environment variable.
Set it in the systemd service so it persists across restarts:

```bash
sudo sed -i '/\[Service\]/a Environment="S3_BUCKET=your-bucket-name-here"' \
  /etc/systemd/system/flask-backend.service

sudo systemctl daemon-reload
sudo systemctl restart flask-backend
```

Replace `your-bucket-name-here` with the same bucket name you used in the
configuration step.

#### 5. Fix log file permissions (first time only)

```bash
sudo touch /var/log/flask-backend-access.log /var/log/flask-backend-error.log
sudo chown ec2-user:ec2-user /var/log/flask-backend-access.log /var/log/flask-backend-error.log
sudo systemctl restart flask-backend
```

#### 6. Fix nginx default server conflict (first time only)

```bash
sudo sed -i '/^    server {/,/^    }/d' /etc/nginx/nginx.conf
sudo nginx -t && sudo systemctl reload nginx
```

#### 7. Verify

```bash
curl http://localhost/health
# Expected: {"status":"ok"}
```

Then from your PC:
```powershell
Invoke-RestMethod -Method POST -Uri "http://<EC2-IP>/auth/login" `
  -ContentType "application/json" `
  -Body '{"email":"sXXXXXXX0@student.rmit.edu.au","password":"012345"}'
```

#### Useful commands on the EC2 instance

```bash
# Check service status
sudo systemctl status flask-backend

# View live logs
sudo journalctl -u flask-backend -f

# Restart after a code change
sudo systemctl restart flask-backend
```

---

## API Reference

### Auth

| Method | Endpoint         | Description                    |
|--------|------------------|--------------------------------|
| POST   | /auth/login      | Validate email + password      |
| POST   | /auth/register   | Register a new user            |
| POST   | /auth/logout     | Acknowledge logout (stateless) |

### Music

| Method | Endpoint      | Description                                      |
|--------|---------------|--------------------------------------------------|
| GET    | /music/query  | Query songs by title, artist, year, album (AND)  |

### Subscriptions

| Method | Endpoint       | Description                        |
|--------|----------------|------------------------------------|
| GET    | /subscriptions | List a user's subscribed songs     |
| POST   | /subscriptions | Subscribe to a song                |
| DELETE | /subscriptions | Remove a subscription              |

---

## DynamoDB Key Schema — Design Rationale

The `music` table uses `title` as the partition key and `artist#year` as a
composite sort key. Song titles alone are not unique (e.g. "Bad Blood" appears
for multiple artists), and even `(title, artist)` is not fully unique — e.g.
"Delicate" by Taylor Swift appears across two album editions in different years.
Only `(title, artist, year)` is unique across all 137 songs, so the sort key
encodes both as `"artist#year"` (e.g. `"Taylor Swift#2017"`).

The **GSI** (`artist-index`) supports the most common query pattern: finding
all songs by a given artist, optionally filtered by year.

The **LSI** (`title-year-index`) supports range queries over year within a
given title partition, useful when searching by title and year together.

The **subscriptions** table uses `email` as the partition key and a composite
`song_id` (`title#artist#year`) as the sort key. This lets a single Query
fetch all of a user's subscriptions, and a single DeleteItem remove one by
its exact key — no scans required.

---

## Part 3 — ECS Fargate Backend

The ECS backend runs the **same Flask application** as EC2, packaged as a Docker
container and managed by Amazon ECS (Fargate). Instead of nginx → gunicorn on a
persistent VM, gunicorn binds directly to port 80 inside the container and ECS
manages container scheduling, health checks, and restarts automatically.

> **AWS Academy — Important IP note:** ECS Fargate tasks are assigned a **new
> public IP every time the task restarts** (e.g. after a lab session ends and
> restarts). Before every demo session, re-run `python deploy/deploy.py` to get
> the current IP and update `frontend/config.js` accordingly. The script skips
> all existing resources and only takes ~30 seconds on subsequent runs.

---

### Local Testing (Python — no Docker needed)

Because the ECS backend is the same Flask application as EC2, you can run and
test it directly with Python. This validates all application logic — DynamoDB
queries, S3 presigned URLs, subscriptions — against the real AWS services,
without needing Docker at all.

**Prerequisites:** Active AWS Academy credentials in `~/.aws/credentials`.

```powershell
cd backend\ecs
pip install -r requirements.txt
python app.py
```

The server starts on `http://localhost:5000`. Test all endpoints in a second terminal:

```powershell
# Health check
Invoke-RestMethod -Uri "http://localhost:5000/health"

# Login (replace with your actual seed email)
Invoke-RestMethod -Method POST -Uri "http://localhost:5000/auth/login" `
  -ContentType "application/json" `
  -Body '{"email":"sXXXXXXX0@student.rmit.edu.au","password":"012345"}'

# Query by artist
Invoke-RestMethod -Uri "http://localhost:5000/music/query?artist=Taylor Swift"

# Query by artist + album (AND logic)
Invoke-RestMethod -Uri "http://localhost:5000/music/query?artist=Taylor Swift&album=Fearless"

# Subscribe to a song
Invoke-RestMethod -Method POST -Uri "http://localhost:5000/subscriptions" `
  -ContentType "application/json" `
  -Body '{"email":"sXXXXXXX0@student.rmit.edu.au","title":"Love Story","artist":"Taylor Swift","year":"2008","album":"Fearless","image_url":"https://raw.githubusercontent.com/YingZhang2015/cc/main/TaylorSwift.jpg"}'

# List subscriptions
Invoke-RestMethod -Uri "http://localhost:5000/subscriptions?email=sXXXXXXX0@student.rmit.edu.au"

# Remove a subscription
Invoke-RestMethod -Method DELETE -Uri "http://localhost:5000/subscriptions" `
  -ContentType "application/json" `
  -Body '{"email":"sXXXXXXX0@student.rmit.edu.au","title":"Love Story","artist":"Taylor Swift","year":"2008"}'
```

> **Note:** AWS credentials are required even for local testing because all data
> lives in AWS (DynamoDB tables and S3 bucket). The Flask server runs locally
> but every request reaches out to real AWS services.

---

### AWS Deployment (ECS Fargate)

**Prerequisites:**
- **Docker Desktop** installed and running (green "Engine running" status)
- Active AWS Academy credentials in `~/.aws/credentials`
- No AWS CLI required — the deploy script uses Python + boto3

#### 1. Refresh AWS credentials

Go to AWS Academy → start your lab → **AWS Details** → **AWS CLI** → **Copy**,
then paste the block into `C:\Users\<you>\.aws\credentials`. (This step is skippable if you have already configured your AWS credentials.)

#### 2. Run the Python deploy script

```powershell
cd "C:\path\to\Cloud_Computing_A2\backend\ecs"
python deploy/deploy.py
```

The script runs 10 steps automatically (skipping anything that already exists):

| Step | What it does |
|---|---|
| 1 | Resolves your AWS account ID |
| 2 | Creates an ECR repository (`music-backend`) |
| 3 | Authenticates Docker to ECR |
| 4 | Builds the Docker image and pushes it to ECR |
| 5 | Creates a CloudWatch log group (`/ecs/music-backend`) |
| 6 | Creates a security group allowing inbound HTTP on port 80 |
| 7 | Registers the ECS task definition with LabRole |
| 8 | Creates the ECS cluster (`music-app-cluster`) |
| 8b | Creates the ECS service-linked role (required in AWS Academy accounts) |
| 9 | Creates the Fargate service with a public IP |
| 10 | Waits for the task to reach RUNNING and prints the public IP |

When complete, the script prints:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 Deployment complete!
 Public IP   : <YOUR_IP>
 Health check: http://<YOUR_IP>/health
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

#### 3. Test all endpoints against the live ECS task

```powershell
$ECS = "http://<YOUR_ECS_IP>"

# Health check
Invoke-RestMethod -Uri "$ECS/health"

# Login
Invoke-RestMethod -Method POST -Uri "$ECS/auth/login" `
  -ContentType "application/json" `
  -Body '{"email":"sXXXXXXX0@student.rmit.edu.au","password":"012345"}'

# Query by artist
Invoke-RestMethod -Uri "$ECS/music/query?artist=Taylor Swift"

# Query by artist + album (AND logic)
Invoke-RestMethod -Uri "$ECS/music/query?artist=Taylor Swift&album=Fearless"

# Subscribe
Invoke-RestMethod -Method POST -Uri "$ECS/subscriptions" `
  -ContentType "application/json" `
  -Body '{"email":"sXXXXXXX0@student.rmit.edu.au","title":"Love Story","artist":"Taylor Swift","year":"2008","album":"Fearless","image_url":"https://raw.githubusercontent.com/YingZhang2015/cc/main/TaylorSwift.jpg"}'

# List subscriptions
Invoke-RestMethod -Uri "$ECS/subscriptions?email=sXXXXXXX0@student.rmit.edu.au"

# Remove subscription
Invoke-RestMethod -Method DELETE -Uri "$ECS/subscriptions" `
  -ContentType "application/json" `
  -Body '{"email":"sXXXXXXX0@student.rmit.edu.au","title":"Love Story","artist":"Taylor Swift","year":"2008"}'
```

#### 4. Point the frontend at ECS

Update `frontend/config.js` to use the ECS IP:

```js
const API_BASE_URL = "http://<YOUR_ECS_IP>";
```

#### 5. Subsequent deploys (after code changes or lab restart)

```powershell
python deploy/deploy.py
```

The script is idempotent — it skips any resources that already exist and only
rebuilds and pushes the Docker image if needed, then updates the running service.

#### Useful links after deployment

| Resource | Where to find it |
|---|---|
| Running tasks | ECS Console → Clusters → `music-app-cluster` → Services → `music-backend-service` → Tasks |
| Container logs | CloudWatch → Log groups → `/ecs/music-backend` |
| Current public IP | ECS task → Network → Public IP (changes on each lab restart) |

---

## Part 4 — API Gateway + Lambda Backend

The Lambda backend is **functionally identical** to the EC2 backend — same
endpoints, same DynamoDB tables, same S3 bucket. Only the compute layer
differs: Flask + gunicorn is replaced by Lambda handlers, and nginx + EC2 is
replaced by API Gateway.

---

### Prerequisites

- [AWS SAM CLI](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html) installed
- Active AWS credentials (`~/.aws/credentials` refreshed from AWS Academy — see [AWS Credentials](#aws-credentials))
- Python 3.13 installed and on your PATH

> **Note on Python version:** The SAM template uses `Runtime: python3.13`. If
> your machine has a different Python version, either update the `Runtime` field
> in `template.yaml` → `Globals.Function` to match your version, or run
> `sam build --use-container` to build inside Docker instead (no local Python
> version requirement).

---

### Local Testing — Option A: Direct handler invocation (no Docker needed)

The fastest way to validate all Lambda logic. Calls the handler functions
directly with mock API Gateway events against the real DynamoDB tables and S3
bucket — no SAM CLI or Docker required, only active AWS credentials.

> Make sure you've updated `_SEED_EMAIL` in `test_local.py` to your own seed
> user email before running (see [Required Configuration](#before-you-start--required-configuration)).

```powershell
cd backend\lambda
pip install -r requirements.txt
python test_local.py
```

Prints a ✓/✗ summary for ~15 test cases covering login, register, query,
subscribe, unsubscribe, and error paths.

---

### Local Testing — Option B: SAM local API server (full API Gateway simulation)

Starts a local HTTP server on port 3000 that behaves exactly like API Gateway,
running each Lambda function inside a Docker container.

**Additional prerequisite:** Docker Desktop running.

```powershell
cd backend\lambda
sam build
sam local start-api
```

Then test with PowerShell against `http://localhost:3000`:

```powershell
# Login (replace with your seed email)
Invoke-RestMethod -Method POST `
  -Uri "http://localhost:3000/auth/login" `
  -ContentType "application/json" `
  -Body '{"email":"sXXXXXXX0@student.rmit.edu.au","password":"012345"}'

# Query by artist
Invoke-RestMethod -Uri "http://localhost:3000/music/query?artist=Taylor Swift"

# Query by artist + album (AND logic)
Invoke-RestMethod -Uri "http://localhost:3000/music/query?artist=Taylor Swift&album=Fearless"

# Subscribe
Invoke-RestMethod -Method POST `
  -Uri "http://localhost:3000/subscriptions" `
  -ContentType "application/json" `
  -Body '{"email":"sXXXXXXX0@student.rmit.edu.au","title":"Love Story","artist":"Taylor Swift","year":"2008","album":"Fearless","image_url":"https://example.com/TaylorSwift.jpg"}'

# List subscriptions
Invoke-RestMethod -Uri "http://localhost:3000/subscriptions?email=sXXXXXXX0@student.rmit.edu.au"

# Unsubscribe
Invoke-RestMethod -Method DELETE `
  -Uri "http://localhost:3000/subscriptions" `
  -ContentType "application/json" `
  -Body '{"email":"sXXXXXXX0@student.rmit.edu.au","title":"Love Story","artist":"Taylor Swift","year":"2008"}'
```

---

### AWS Deployment

#### 1. Get your LabRole ARN

In the AWS Console go to **IAM → Roles → LabRole** and copy the ARN. It follows
the format:
```
arn:aws:iam::<YOUR_ACCOUNT_ID>:role/LabRole
```

Your account ID is visible on the IAM Roles page next to the LabRole entry.

#### 2. Build

```powershell
cd backend\lambda
sam build
```

#### 3. Deploy (first time — interactive)

```powershell
sam deploy --guided --parameter-overrides LabRoleArn=arn:aws:iam::<YOUR_ACCOUNT_ID>:role/LabRole
```

Answer the prompts as follows:

| Prompt | Answer |
|--------|--------|
| Stack Name | `music-app-lambda` |
| AWS Region | `us-east-1` |
| Parameter LabRoleArn | *(your LabRole ARN)* |
| Confirm changes before deploy | `y` |
| Allow SAM CLI IAM role creation | `n` |
| Disable rollback | `n` |
| `*Function` may not have authorization defined... | `y` (×7) |
| Capabilities | *(press Enter to accept default `CAPABILITY_IAM`)* |
| Save arguments to samconfig.toml | `y` |
| SAM configuration file | `samconfig.toml` |
| SAM configuration environment | `default` |

SAM will display a changeset preview and ask `Deploy this changeset? [y/N]` —
type `y`. Deployment takes ~1–2 minutes.

#### 4. Get your API URL

After deployment the Outputs table is printed to the terminal:

```
Key    ApiBaseUrl
Value  https://<YOUR_API_ID>.execute-api.us-east-1.amazonaws.com/prod
```

Copy the `ApiBaseUrl` value — this is your live API base URL. Use it as the
backend URL in your frontend config.

#### 5. Verify

```powershell
# Set your base URL once
$API = "https://<YOUR_API_ID>.execute-api.us-east-1.amazonaws.com/prod"

# Login
Invoke-RestMethod -Method POST `
  -Uri "$API/auth/login" `
  -ContentType "application/json" `
  -Body '{"email":"sXXXXXXX0@student.rmit.edu.au","password":"012345"}'

# Query by artist
Invoke-RestMethod -Uri "$API/music/query?artist=Taylor Swift"

# Subscribe
Invoke-RestMethod -Method POST `
  -Uri "$API/subscriptions" `
  -ContentType "application/json" `
  -Body '{"email":"sXXXXXXX0@student.rmit.edu.au","title":"Love Story","artist":"Taylor Swift","year":"2008","album":"Fearless","image_url":"https://example.com/TaylorSwift.jpg"}'

# List subscriptions
Invoke-RestMethod -Uri "$API/subscriptions?email=sXXXXXXX0@student.rmit.edu.au"

# Unsubscribe
Invoke-RestMethod -Method DELETE `
  -Uri "$API/subscriptions" `
  -ContentType "application/json" `
  -Body '{"email":"sXXXXXXX0@student.rmit.edu.au","title":"Love Story","artist":"Taylor Swift","year":"2008"}'
```

#### 6. Subsequent deploys (after code changes)

```powershell
sam build && sam deploy
```

No prompts — uses the saved `samconfig.toml` from the first deploy.

---

### Tear Down

```powershell
sam delete --stack-name music-app-lambda
```

Removes the API Gateway, all 7 Lambda functions, and the CloudFormation stack.
DynamoDB tables and the S3 bucket are **not** deleted (shared with EC2/ECS).

---

### Lambda API Reference

| Method | Path              | Lambda Handler                                        |
|--------|-------------------|-------------------------------------------------------|
| POST   | /auth/login       | `handlers.auth.login_handler`                         |
| POST   | /auth/register    | `handlers.auth.register_handler`                      |
| POST   | /auth/logout      | `handlers.auth.logout_handler`                        |
| GET    | /music/query      | `handlers.music.query_handler`                        |
| GET    | /subscriptions    | `handlers.subscriptions.list_handler`                 |
| POST   | /subscriptions    | `handlers.subscriptions.subscribe_handler`            |
| DELETE | /subscriptions    | `handlers.subscriptions.unsubscribe_handler`          |

---

## AWS Resources

| Resource              | Name                                       |
|-----------------------|--------------------------------------------|
| DynamoDB table        | `login`                                    |
| DynamoDB table        | `music`                                    |
| DynamoDB table        | `subscriptions`                            |
| S3 bucket             | your bucket name (see configuration above) |
| EC2 instance          | Amazon Linux 2023, t3.micro                |
| ECR repository        | `music-backend`                            |
| ECS cluster           | `music-app-cluster`                        |
| ECS service           | `music-backend-service` (Fargate)          |
| API Gateway REST API  | `MusicApi` (via SAM stack)                 |
| Lambda functions (×7) | `music-app-auth-*`, `music-app-music-*`, `music-app-subscriptions-*` |
