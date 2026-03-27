#!/bin/bash
set -e

echo "🚀 Starting job..."

# -------------------------------
# Force SF CLI config location
# -------------------------------
export SF_HOME=/tmp/sf
mkdir -p $SF_HOME

# -------------------------------
# Install SF CLI
# -------------------------------
echo "📦 Installing SF CLI..."
curl -sL https://developer.salesforce.com/media/salesforce-cli/sf/channels/stable/sf-linux-x64.tar.xz -o sf.tar.xz
mkdir -p /tmp/sf-cli
tar -xJf sf.tar.xz -C /tmp/sf-cli --strip-components 1
export PATH=/tmp/sf-cli/bin:$PATH

sf version

# -------------------------------
# Auth
# -------------------------------
echo "🔐 Logging in..."

sf org login jwt \
  --username "$SF_USERNAME" \
  --client-id "$SF_CLIENT_ID" \
  --jwt-key-file "$SF_JWT_KEY_FILE" \
  --instance-url "$SF_INSTANCE_URL"

echo "✅ Login done"

# -------------------------------
# DEBUG (IMPORTANT)
# -------------------------------
echo "📌 SF_HOME=$SF_HOME"
ls -la $SF_HOME

echo "🔍 Checking org list..."
sf org list --all

# -------------------------------
# Deploy (use username, NOT alias)
# -------------------------------
echo "🚀 Deploying..."

sf project deploy start \
  --target-org "$SF_USERNAME" \
  --source-dir force-app \
  --wait 20

echo "✅ Deployment finished"
