# 1. Login via JWT (get token)
LOGIN_OUTPUT=$(sf org login jwt \
  --username "$SF_USERNAME" \
  --client-id "$SF_CLIENT_ID" \
  --jwt-key-file "$SF_JWT_KEY_FILE" \
  --instance-url "$SF_INSTANCE_URL" \
  --json)

# 2. Extract token + URL
ACCESS_TOKEN=$(echo $LOGIN_OUTPUT | jq -r '.result.accessToken')
INSTANCE_URL=$(echo $LOGIN_OUTPUT | jq -r '.result.instanceUrl')

# 3. Register this session as an org (IMPORTANT STEP)
sf org login access-token \
  --access-token "$ACCESS_TOKEN" \
  --instance-url "$INSTANCE_URL" \
  --alias ci-org

# 4. Deploy using alias
sf project deploy start \
  --target-org ci-org \
  --source-dir force-app
