#!/bin/bash
# EC2 User Data Script - Paste this in "User Data" when launching EC2 instance

# Update system
yum update -y

# Install Python 3 and pip
yum install -y python3 python3-pip git

# Create app directory
mkdir -p /home/ec2-user/cloudwatch-logs-viewer
cd /home/ec2-user/cloudwatch-logs-viewer

# Create requirements.txt
cat > requirements.txt <<'EOF'
Flask==3.0.0
boto3==1.34.0
gunicorn==21.2.0
EOF

# Install dependencies
pip3 install -r requirements.txt

# Note: You still need to upload app.py and templates/index.html manually
# Or clone from git repository

echo "EC2 setup complete. Upload your application files to /home/ec2-user/cloudwatch-logs-viewer/"
