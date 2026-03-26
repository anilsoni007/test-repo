#!/bin/bash
# ============================================================
# Basic Salesforce Deployment — Jenkins on EKS
# Auth  : JWT Bearer Flow (External Client App)
# Note  : Fresh pod per job — SF CLI installed at runtime
# ============================================================

set -e

# ── Variables (injected as Jenkins env vars / credentials) ──
SF_USERNAME="${SF_USERNAME}"           # e.g. deploy@myorg.sandbox
SF_CLIENT_ID="${SF_CLIENT_ID}"         # External Client App → Client ID
SF_JWT_KEY_FILE="${SF_JWT_KEY_FILE}"   # Path to server.key (mounted as Jenkins secret)
SF_INSTANCE_URL="https://test.salesforce.com"  # Sandbox URL

echo "========================================"
echo " Salesforce Deployment — Build #${BUILD_NUMBER}"
echo "========================================"

# ── Step 1: Install SF CLI ──
echo "[1] Installing Salesforce CLI..."

# Detect package manager and install accordingly
if command -v npm &>/dev/null; then
    echo "Using npm to install SF CLI..."
    npm install -g @salesforce/cli --quiet
elif command -v apt-get &>/dev/null; then
    echo "Using apt to install SF CLI..."
    apt-get update -qq
    apt-get install -y wget
    wget -q https://developer.salesforce.com/media/salesforce-cli/sf/channels/stable/sf-linux-x64.tar.xz
    mkdir -p /usr/local/sf
    tar xJf sf-linux-x64.tar.xz -C /usr/local/sf --strip-components=1
    ln -sf /usr/local/sf/bin/sf /usr/local/bin/sf
    rm -f sf-linux-x64.tar.xz
else
    echo "No supported package manager found (npm or apt). Exiting."
    exit 1
fi

# ── Step 2: Verify SF CLI installed ──
echo "[2] Checking SF CLI..."
sf --version

# ── Step 3: Authenticate ──
echo "[3] Authenticating to Salesforce..."
sf org login jwt \
  --username     "$SF_USERNAME" \
  --client-id    "$SF_CLIENT_ID" \
  --jwt-key-file "$SF_JWT_KEY_FILE" \
  --instance-url "$SF_INSTANCE_URL" \
  --alias        deploy-org \
  --set-default

echo "Auth successful!"

# ── Step 4: Verify org connection ──
echo "[4] Verifying org..."
sf org display --target-org deploy-org

# ── Step 5: Deploy source ──
echo "[5] Deploying..."
sf project deploy start \
  --source-dir  force-app \
  --target-org  deploy-org \
  --test-level  RunLocalTests \
  --wait        30

echo "Deployment complete!"

# ── Step 6: Logout ──
echo "[6] Logging out..."
sf org logout --target-org deploy-org --no-prompt

echo "Done!"
