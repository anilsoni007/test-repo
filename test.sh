#!/bin/bash
set -e  # Exit on error

echo "🚀 Starting Salesforce Deployment..."

# -------------------------------
# 1. Install Salesforce CLI
# -------------------------------
echo "📦 Installing Salesforce CLI..."

curl -sL https://developer.salesforce.com/media/salesforce-cli/sf/channels/stable/sf-linux-x64.tar.xz -o sf.tar.xz

mkdir -p ~/sf
tar -xJf sf.tar.xz -C ~/sf --strip-components 1

export PATH=$HOME/sf/bin:$PATH

sf version

# -------------------------------
# 2. Authenticate using JWT
# -------------------------------
echo "🔐 Authenticating to Salesforce..."

sf org login jwt \
  --username "$SF_USERNAME" \
  --client-id "$SF_CLIENT_ID" \
  --jwt-key-file "$SF_JWT_KEY_FILE" \
  --instance-url "$SF_INSTANCE_URL" \
  --alias my-org \
  --set-default

echo "✅ Authentication successful"

# -------------------------------
# 3. Deploy Metadata
# -------------------------------
echo "📦 Starting Deployment..."

sf project deploy start \
  --source-dir force-app \
  --target-org my-org \
  --wait 10

echo "✅ Deployment completed successfully"
