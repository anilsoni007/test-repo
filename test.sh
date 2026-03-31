#!/bin/bash
set -e

echo "📦 Installing dependencies..."
apk add --no-cache jq curl tar xz 2>/dev/null || true

echo "📦 Installing SF CLI..."
curl -sL https://developer.salesforce.com/media/salesforce-cli/sf/channels/stable/sf-linux-x64.tar.xz -o sf.tar.xz
mkdir -p /tmp/sf-cli
tar -xJf sf.tar.xz -C /tmp/sf-cli --strip-components 1
export PATH=/tmp/sf-cli/bin:$PATH

echo "🔐 Logging in (stateless)..."

LOGIN_OUTPUT=$(sf org login jwt \
  --username "$SF_USERNAME" \
  --client-id "$SF_CLIENT_ID" \
  --jwt-key-file "$SF_JWT_KEY_FILE" \
  --instance-url "$SF_INSTANCE_URL" \
  --json)

echo "$LOGIN_OUTPUT"

ACCESS_TOKEN=$(echo $LOGIN_OUTPUT | jq -r '.result.accessToken')
INSTANCE_URL=$(echo $LOGIN_OUTPUT | jq -r '.result.instanceUrl')

echo "🚀 Deploying using access token..."

sf project deploy start \
  --target-org "$ACCESS_TOKEN" \
  --instance-url "$INSTANCE_URL" \
  --source-dir force-app \
  --wait 20

echo "✅ Deployment done"
