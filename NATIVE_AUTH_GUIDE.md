# Native Authentication Deployment Guide
## Using RDS PostgreSQL for User Management

This guide shows how to deploy the CloudWatch Logs Viewer with native login (no Cognito).

---

## Architecture

```
User → ALB (HTTPS) → EKS Pods → RDS PostgreSQL
                         ↓
                   CloudWatch Logs
```

---

## Step 1: Create RDS PostgreSQL Database

### Option A: Using AWS Console

1. Go to RDS Console
2. Create Database
3. Choose PostgreSQL
4. Template: Free tier or Dev/Test
5. Settings:
   - DB instance identifier: `logs-viewer-db`
   - Master username: `postgres`
   - Master password: `<your-secure-password>`
6. Instance configuration: `db.t3.micro` (free tier) or `db.t3.small`
7. Storage: 20 GB
8. VPC: Same as EKS cluster
9. Public access: No
10. VPC security group: Create new or use existing
11. Database name: `logsviewer`
12. Create database

### Option B: Using AWS CLI

```bash
# Get VPC and subnet info from EKS cluster
export VPC_ID=$(aws eks describe-cluster --name logs-viewer-cluster --query 'cluster.resourcesVpcConfig.vpcId' --output text)
export SUBNET_IDS=$(aws eks describe-cluster --name logs-viewer-cluster --query 'cluster.resourcesVpcConfig.subnetIds' --output text | tr '\t' ',')

# Create DB subnet group
aws rds create-db-subnet-group \
  --db-subnet-group-name logs-viewer-db-subnet \
  --db-subnet-group-description "Subnet group for logs viewer DB" \
  --subnet-ids $(echo $SUBNET_IDS | tr ',' ' ')

# Create security group
export SG_ID=$(aws ec2 create-security-group \
  --group-name logs-viewer-db-sg \
  --description "Security group for logs viewer RDS" \
  --vpc-id $VPC_ID \
  --query 'GroupId' \
  --output text)

# Allow PostgreSQL access from EKS nodes
export EKS_SG=$(aws eks describe-cluster --name logs-viewer-cluster --query 'cluster.resourcesVpcConfig.clusterSecurityGroupId' --output text)

aws ec2 authorize-security-group-ingress \
  --group-id $SG_ID \
  --protocol tcp \
  --port 5432 \
  --source-group $EKS_SG

# Create RDS instance
aws rds create-db-instance \
  --db-instance-identifier logs-viewer-db \
  --db-instance-class db.t3.micro \
  --engine postgres \
  --engine-version 15.4 \
  --master-username postgres \
  --master-user-password 'YourSecurePassword123!' \
  --allocated-storage 20 \
  --db-subnet-group-name logs-viewer-db-subnet \
  --vpc-security-group-ids $SG_ID \
  --db-name logsviewer \
  --backup-retention-period 7 \
  --no-publicly-accessible

# Wait for DB to be available (takes 5-10 minutes)
aws rds wait db-instance-available --db-instance-identifier logs-viewer-db

# Get DB endpoint
export DB_HOST=$(aws rds describe-db-instances \
  --db-instance-identifier logs-viewer-db \
  --query 'DBInstances[0].Endpoint.Address' \
  --output text)

echo "DB Host: $DB_HOST"
```

---

## Step 2: Initialize Database Schema

```bash
# Save DB credentials
export DB_HOST="<your-rds-endpoint>.rds.amazonaws.com"
export DB_PORT="5432"
export DB_NAME="logsviewer"
export DB_USER="postgres"
export DB_PASSWORD="YourSecurePassword123!"

# Connect to database and run init script
PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -f db/init.sql

# Verify table created
PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -c "\dt"
```

---

## Step 3: Add Users to Database

### Method 1: Using the script

```bash
# Make script executable
chmod +x db/add-user.sh

# Add users
export DB_HOST="<your-rds-endpoint>.rds.amazonaws.com"
export DB_PASSWORD="YourSecurePassword123!"

./db/add-user.sh "developer1@company.com" "Developer One" "DevPass123!"
./db/add-user.sh "developer2@company.com" "Developer Two" "DevPass456!"
```

### Method 2: Direct SQL

```bash
PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME <<EOF
INSERT INTO users (email, name, password_hash) 
VALUES ('developer1@company.com', 'Developer One', crypt('DevPass123!', gen_salt('bf')));

INSERT INTO users (email, name, password_hash) 
VALUES ('developer2@company.com', 'Developer Two', crypt('DevPass456!', gen_salt('bf')));
EOF
```

### Method 3: Using psql interactively

```bash
PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME

-- Then run:
INSERT INTO users (email, name, password_hash) 
VALUES ('user@company.com', 'User Name', crypt('Password123!', gen_salt('bf')));

-- List all users:
SELECT id, email, name, is_active, created_at FROM users;

-- Deactivate a user:
UPDATE users SET is_active = false WHERE email = 'user@company.com';

-- Activate a user:
UPDATE users SET is_active = true WHERE email = 'user@company.com';

-- Delete a user:
DELETE FROM users WHERE email = 'user@company.com';
```

---

## Step 4: Create IAM Role for CloudWatch Access

### 4.1 Create IAM Policy

```bash
cat > cloudwatch-logs-policy.json <<'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "logs:DescribeLogGroups",
        "logs:DescribeLogStreams",
        "logs:FilterLogEvents"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "lex:ListBots",
        "lex:ListBotAliases",
        "lex:DescribeBotAlias"
      ],
      "Resource": "*"
    }
  ]
}
EOF

aws iam create-policy \
  --policy-name CloudWatchLogsViewerPolicy \
  --policy-document file://cloudwatch-logs-policy.json
```

### 4.2 Create Service Account with IRSA

```bash
export CLUSTER_NAME=logs-viewer-cluster
export REGION=us-east-1
export ACCOUNT_ID=170928836252

eksctl create iamserviceaccount \
  --name cloudwatch-logs-viewer-sa \
  --namespace default \
  --cluster $CLUSTER_NAME \
  --region $REGION \
  --attach-policy-arn arn:aws:iam::${ACCOUNT_ID}:policy/CloudWatchLogsViewerPolicy \
  --approve \
  --override-existing-serviceaccounts

# Verify
kubectl get sa cloudwatch-logs-viewer-sa -o yaml
```

---

## Step 5: Build and Push Docker Image

```bash
cd d:/test-repo

# Build
docker build -t log-shipper .

# Tag
docker tag log-shipper:latest 170928836252.dkr.ecr.us-east-1.amazonaws.com/log-shipper:latest

# Push
docker push 170928836252.dkr.ecr.us-east-1.amazonaws.com/log-shipper:latest
```

---

## Step 6: Create Kubernetes Secret

```bash
kubectl create secret generic app-secrets \
  --from-literal=SECRET_KEY=$(openssl rand -hex 32) \
  --from-literal=DB_HOST="<your-rds-endpoint>.rds.amazonaws.com" \
  --from-literal=DB_PORT="5432" \
  --from-literal=DB_NAME="logsviewer" \
  --from-literal=DB_USER="postgres" \
  --from-literal=DB_PASSWORD="YourSecurePassword123!" \
  --dry-run=client -o yaml | kubectl apply -f -

# Verify
kubectl get secret app-secrets
```

---

## Step 7: Deploy Application

```bash
# Deploy using all-in-one.yaml
kubectl apply -f k8s/all-in-one.yaml

# Check status
kubectl get pods -l app=cloudwatch-logs-viewer
kubectl logs -l app=cloudwatch-logs-viewer --tail=50
```

---

## Step 8: Test Login

1. Visit: `https://log-shipper-app.170928836252.realhandsonlabs.net`
2. Should see login page
3. Enter email and password
4. Should redirect to logs viewer

---

## User Management Commands

### List all users
```sql
SELECT id, email, name, is_active, created_at, last_login FROM users ORDER BY created_at DESC;
```

### Add user
```sql
INSERT INTO users (email, name, password_hash) 
VALUES ('newuser@company.com', 'New User', crypt('Password123!', gen_salt('bf')));
```

### Update password
```sql
UPDATE users 
SET password_hash = crypt('NewPassword123!', gen_salt('bf')), 
    updated_at = CURRENT_TIMESTAMP 
WHERE email = 'user@company.com';
```

### Deactivate user
```sql
UPDATE users SET is_active = false WHERE email = 'user@company.com';
```

### Activate user
```sql
UPDATE users SET is_active = true WHERE email = 'user@company.com';
```

### Delete user
```sql
DELETE FROM users WHERE email = 'user@company.com';
```

---

## Quick Commands

```bash
# Connect to database
PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME

# Add user via script
./db/add-user.sh "user@company.com" "User Name" "Password123!"

# View app logs
kubectl logs -l app=cloudwatch-logs-viewer -f

# Restart app
kubectl rollout restart deployment/cloudwatch-logs-viewer

# Check database connection from pod
kubectl exec -it deployment/cloudwatch-logs-viewer -- env | grep DB_
```

---

## Troubleshooting

### Can't connect to database
```bash
# Check security group allows traffic from EKS
# Check DB is in same VPC as EKS
# Test connection from pod
kubectl run -it --rm debug --image=postgres:15 --restart=Never -- \
  psql -h $DB_HOST -U $DB_USER -d $DB_NAME
```

### Login not working
```bash
# Check user exists and is active
PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME \
  -c "SELECT * FROM users WHERE email = 'user@company.com';"

# Check app logs
kubectl logs -l app=cloudwatch-logs-viewer --tail=100
```

### Password not working
```bash
# Reset password
PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME <<EOF
UPDATE users 
SET password_hash = crypt('NewPassword123!', gen_salt('bf')) 
WHERE email = 'user@company.com';
EOF
```

---

## Cost Estimate

**~$165/month:**
- EKS Cluster: $73/month
- EC2 Nodes (2x t3.medium): $60/month
- ALB: $16/month
- RDS db.t3.micro: $15/month
- Route53: $0.50/month

---

## Benefits of Native Auth

✅ No Cognito complexity
✅ Full control over users
✅ Simple password management
✅ Easy to add/remove users
✅ No external dependencies
✅ Works offline (for local dev)

---

**You're done! Users can now login with email/password stored in RDS.**
