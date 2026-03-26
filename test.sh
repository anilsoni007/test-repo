#!/bin/bash
# ============================================================
# Basic Salesforce Deployment — Jenkins on EKS
# Auth  : JWT Bearer Flow (External Client App)
# Note  : Fresh pod per job — SF CLI installed at runtime
# OS    : Auto-detects apt / yum / npm for CLI installation
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

# ── Step 1: Install SF CLI (auto-detect package manager) ──
echo "[1] Installing Salesforce CLI..."

install_sf_cli() {

    # ── Option A: npm ──────────────────────────────────────
    if command -v npm &>/dev/null; then
        echo "Detected: npm"
        npm install -g @salesforce/cli --quiet
        return 0
    fi

    # ── Option B: apt-get (Debian / Ubuntu) ────────────────
    if command -v apt-get &>/dev/null; then
        echo "Detected: apt-get (Debian/Ubuntu)"
        apt-get update -qq
        apt-get install -y wget ca-certificates
        wget -q https://developer.salesforce.com/media/salesforce-cli/sf/channels/stable/sf-linux-x64.tar.xz
        mkdir -p /usr/local/sf
        tar xJf sf-linux-x64.tar.xz -C /usr/local/sf --strip-components=1
        ln -sf /usr/local/sf/bin/sf /usr/local/bin/sf
        rm -f sf-linux-x64.tar.xz
        return 0
    fi

    # ── Option C: yum (RHEL / CentOS / Amazon Linux) ───────
    if command -v yum &>/dev/null; then
        echo "Detected: yum (RHEL/CentOS/Amazon Linux)"
        yum install -y wget tar xz
        wget -q https://developer.salesforce.com/media/salesforce-cli/sf/channels/stable/sf-linux-x64.tar.xz
        mkdir -p /usr/local/sf
        tar xJf sf-linux-x64.tar.xz -C /usr/local/sf --strip-components=1
        ln -sf /usr/local/sf/bin/sf /usr/local/bin/sf
        rm -f sf-linux-x64.tar.xz
        return 0
    fi

    # ── No supported package manager found ─────────────────
    echo "ERROR: No supported package manager found (npm / apt-get / yum)."
    echo "       Please use a pod image based on Debian, Ubuntu, RHEL, CentOS, Amazon Linux, or Node.js."
    exit 1
}

install_sf_cli

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
