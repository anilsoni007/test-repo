#!/bin/bash
# EC2 Setup Script for CloudWatch Logs Viewer

# Update system
sudo yum update -y

# Install Python 3 and pip
sudo yum install -y python3 python3-pip git

# Clone or copy application files
cd /home/ec2-user
mkdir -p cloudwatch-logs-viewer
cd cloudwatch-logs-viewer

# Install dependencies
pip3 install -r requirements.txt

# Install and configure systemd service
sudo tee /etc/systemd/system/logs-viewer.service > /dev/null <<EOF
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
EOF

# Start service
sudo systemctl daemon-reload
sudo systemctl enable logs-viewer
sudo systemctl start logs-viewer

echo "Setup complete! Application running on port 5000"
