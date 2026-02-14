# EC2 Deployment Guide

## Prerequisites
- AWS Account with EC2 access
- AWS CLI configured locally (optional)

## Step 1: Launch EC2 Instance

1. **Go to EC2 Console** → Launch Instance

2. **Configure Instance:**
   - **Name:** cloudwatch-logs-viewer
   - **AMI:** Amazon Linux 2023 (or Amazon Linux 2)
   - **Instance Type:** t2.micro (free tier) or t3.small
   - **Key Pair:** Create or select existing key pair
   - **Network Settings:**
     - Allow SSH (port 22) from your IP
     - Allow HTTP (port 80) from anywhere (0.0.0.0/0)
     - Allow Custom TCP (port 5000) from anywhere (for testing)

3. **IAM Role:** Create and attach IAM role with CloudWatch Logs permissions (see below)

4. **Launch Instance**

## Step 2: Create IAM Role

1. Go to **IAM Console** → Roles → Create Role
2. Select **AWS Service** → **EC2**
3. Create policy with these permissions:

```json
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
    }
  ]
}
```

4. Name the role: `CloudWatchLogsViewerRole`
5. Attach role to EC2 instance: EC2 Console → Instance → Actions → Security → Modify IAM Role

## Step 3: Connect and Deploy

### Option A: Manual Deployment

```bash
# Connect to EC2
ssh -i your-key.pem ec2-user@<EC2-PUBLIC-IP>

# Update system
sudo yum update -y

# Install Python and Git
sudo yum install -y python3 python3-pip git

# Create app directory
mkdir cloudwatch-logs-viewer
cd cloudwatch-logs-viewer

# Upload files (from your local machine)
# scp -i your-key.pem -r * ec2-user@<EC2-PUBLIC-IP>:~/cloudwatch-logs-viewer/

# Install dependencies
pip3 install -r requirements.txt

# Test the app
python3 app.py
```

Visit: `http://<EC2-PUBLIC-IP>:5000`

### Option B: Production Deployment with Gunicorn

```bash
# Install gunicorn
pip3 install gunicorn

# Create systemd service
sudo nano /etc/systemd/system/logs-viewer.service
```

Paste this content:

```ini
[Unit]
Description=CloudWatch Logs Viewer
After=network.target

[Service]
Type=simple
User=ec2-user
WorkingDirectory=/home/ec2-user/cloudwatch-logs-viewer
ExecStart=/usr/local/bin/gunicorn -w 4 -b 0.0.0.0:5000 app:app
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
# Start service
sudo systemctl daemon-reload
sudo systemctl enable logs-viewer
sudo systemctl start logs-viewer
sudo systemctl status logs-viewer
```

## Step 4: Upload Files to EC2

From your local machine:

```bash
# Upload all files
scp -i your-key.pem -r app.py requirements.txt templates/ ec2-user@<EC2-PUBLIC-IP>:~/cloudwatch-logs-viewer/
```

## Step 5: Access Application

- **Testing:** `http://<EC2-PUBLIC-IP>:5000`
- **Production:** Set up nginx/ALB for HTTPS (optional)

## Quick Test Commands

```bash
# Check if app is running
curl http://localhost:5000

# View logs
sudo journalctl -u logs-viewer -f

# Restart service
sudo systemctl restart logs-viewer
```

## Optional: Setup Nginx Reverse Proxy (Port 80)

```bash
# Install nginx
sudo yum install -y nginx

# Configure nginx
sudo nano /etc/nginx/nginx.conf
```

Add inside `http` block:

```nginx
server {
    listen 80;
    server_name _;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

```bash
# Start nginx
sudo systemctl enable nginx
sudo systemctl start nginx
```

Now access via: `http://<EC2-PUBLIC-IP>` (port 80)

## Troubleshooting

**App not starting:**
```bash
sudo systemctl status logs-viewer
sudo journalctl -u logs-viewer -n 50
```

**Port already in use:**
```bash
sudo lsof -i :5000
sudo kill -9 <PID>
```

**AWS credentials error:**
- Verify IAM role is attached to EC2 instance
- Check role has CloudWatch Logs permissions

**Connection timeout:**
- Check Security Group allows inbound traffic on port 5000/80
- Verify EC2 instance is running

## Cost Estimate

- **EC2 t2.micro:** Free tier eligible (750 hours/month)
- **CloudWatch API calls:** ~$0.01 per 1000 requests
- **Data transfer:** First 100GB free per month
