# EKS Deployment with AWS Cognito Authentication

## Prerequisites
- EKS cluster running
- AWS CLI configured
- kubectl configured for your EKS cluster
- AWS Load Balancer Controller installed on EKS
- ACM certificate for HTTPS

## Step 1: Create Cognito User Pool

```bash
# Create User Pool
aws cognito-idp create-user-pool \
  --pool-name logs-viewer-users \
  --auto-verified-attributes email \
  --policies "PasswordPolicy={MinimumLength=8,RequireUppercase=true,RequireLowercase=true,RequireNumbers=true}" \
  --region us-east-1 \
  --query 'UserPool.Id' \
  --output text

# Save the User Pool ID
export USER_POOL_ID=<your-user-pool-id>
```

## Step 2: Create Cognito Domain

```bash
# Create a unique domain prefix
aws cognito-idp create-user-pool-domain \
  --domain logs-viewer-$(date +%s) \
  --user-pool-id $USER_POOL_ID \
  --region us-east-1

# Get the domain name
aws cognito-idp describe-user-pool \
  --user-pool-id $USER_POOL_ID \
  --region us-east-1 \
  --query 'UserPool.Domain' \
  --output text

# Save as: logs-viewer-xxx.auth.us-east-1.amazoncognito.com
export COGNITO_DOMAIN=<your-domain>.auth.us-east-1.amazoncognito.com
```

## Step 3: Deploy to EKS (Get ALB URL First)

```bash
# Build and push Docker image
aws ecr create-repository --repository-name cloudwatch-logs-viewer --region us-east-1
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com

docker build -t cloudwatch-logs-viewer .
docker tag cloudwatch-logs-viewer:latest <ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/cloudwatch-logs-viewer:latest
docker push <ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/cloudwatch-logs-viewer:latest

# Update k8s/all-in-one.yaml with your ACCOUNT_ID and REGION
# Deploy WITHOUT Cognito secrets first to get ALB URL
kubectl apply -f k8s/all-in-one.yaml

# Wait for ALB to be created
kubectl get ingress cloudwatch-logs-viewer -w

# Get ALB URL
export ALB_URL=$(kubectl get ingress cloudwatch-logs-viewer -o jsonpath='{.status.loadBalancer.ingress[0].hostname}')
echo "ALB URL: https://$ALB_URL"
```

## Step 4: Create Cognito App Client with ALB URL

```bash
# Now create app client with correct callback URL
aws cognito-idp create-user-pool-client \
  --user-pool-id $USER_POOL_ID \
  --client-name logs-viewer-client \
  --generate-secret \
  --callback-urls "https://$ALB_URL/callback" \
  --logout-urls "https://$ALB_URL" \
  --allowed-o-auth-flows code \
  --allowed-o-auth-scopes openid email profile \
  --allowed-o-auth-flows-user-pool-client \
  --supported-identity-providers COGNITO \
  --region us-east-1

# Save Client ID and Secret
export CLIENT_ID=<your-client-id>
export CLIENT_SECRET=<your-client-secret>
```

## Step 5: Update Kubernetes Secrets

```bash
# Generate random secret key
export SECRET_KEY=$(openssl rand -hex 32)

# Update the secret in k8s/all-in-one.yaml or create directly:
kubectl create secret generic cognito-secrets \
  --from-literal=COGNITO_DOMAIN=$COGNITO_DOMAIN \
  --from-literal=COGNITO_CLIENT_ID=$CLIENT_ID \
  --from-literal=COGNITO_CLIENT_SECRET=$CLIENT_SECRET \
  --from-literal=SECRET_KEY=$SECRET_KEY \
  --dry-run=client -o yaml | kubectl apply -f -

# Update APP_URL in deployment
kubectl set env deployment/cloudwatch-logs-viewer APP_URL=https://$ALB_URL

# Restart pods to pick up new config
kubectl rollout restart deployment/cloudwatch-logs-viewer
```

## Step 6: Add Developers to Cognito

```bash
# Add each developer
aws cognito-idp admin-create-user \
  --user-pool-id $USER_POOL_ID \
  --username developer1@company.com \
  --user-attributes Name=email,Value=developer1@company.com Name=email_verified,Value=true \
  --desired-delivery-mediums EMAIL \
  --region us-east-1

# Repeat for each developer
aws cognito-idp admin-create-user \
  --user-pool-id $USER_POOL_ID \
  --username developer2@company.com \
  --user-attributes Name=email,Value=developer2@company.com Name=email_verified,Value=true \
  --desired-delivery-mediums EMAIL \
  --region us-east-1
```

## Step 7: Bulk Add Developers (Optional)

Create a file `developers.txt`:
```
developer1@company.com
developer2@company.com
developer3@company.com
```

Run script:
```bash
while read email; do
  aws cognito-idp admin-create-user \
    --user-pool-id $USER_POOL_ID \
    --username "$email" \
    --user-attributes Name=email,Value="$email" Name=email_verified,Value=true \
    --desired-delivery-mediums EMAIL \
    --region us-east-1
  echo "Added: $email"
done < developers.txt
```

## Step 8: Verify Deployment

```bash
# Check pods
kubectl get pods -l app=cloudwatch-logs-viewer

# Check logs
kubectl logs -l app=cloudwatch-logs-viewer --tail=50

# Access the application
echo "Application URL: https://$ALB_URL"
```

## Managing Users

### List all users:
```bash
aws cognito-idp list-users \
  --user-pool-id $USER_POOL_ID \
  --region us-east-1
```

### Delete a user:
```bash
aws cognito-idp admin-delete-user \
  --user-pool-id $USER_POOL_ID \
  --username developer@company.com \
  --region us-east-1
```

### Reset user password:
```bash
aws cognito-idp admin-reset-user-password \
  --user-pool-id $USER_POOL_ID \
  --username developer@company.com \
  --region us-east-1
```

### Disable a user:
```bash
aws cognito-idp admin-disable-user \
  --user-pool-id $USER_POOL_ID \
  --username developer@company.com \
  --region us-east-1
```

### Enable a user:
```bash
aws cognito-idp admin-enable-user \
  --user-pool-id $USER_POOL_ID \
  --username developer@company.com \
  --region us-east-1
```

## Troubleshooting

### Check Cognito configuration:
```bash
kubectl exec -it deployment/cloudwatch-logs-viewer -- env | grep COGNITO
```

### View application logs:
```bash
kubectl logs -l app=cloudwatch-logs-viewer -f
```

### Test authentication flow:
1. Visit `https://$ALB_URL`
2. Should redirect to Cognito login
3. Login with developer credentials
4. Should redirect back to application

## Security Best Practices

1. **Use HTTPS only** - Already configured in all-in-one.yaml
2. **Rotate secrets regularly**:
   ```bash
   kubectl create secret generic cognito-secrets \
     --from-literal=SECRET_KEY=$(openssl rand -hex 32) \
     --dry-run=client -o yaml | kubectl apply -f -
   kubectl rollout restart deployment/cloudwatch-logs-viewer
   ```

3. **Enable MFA** (optional):
   ```bash
   aws cognito-idp set-user-pool-mfa-config \
     --user-pool-id $USER_POOL_ID \
     --mfa-configuration OPTIONAL \
     --software-token-mfa-configuration Enabled=true \
     --region us-east-1
   ```

4. **Set password expiration**:
   ```bash
   aws cognito-idp update-user-pool \
     --user-pool-id $USER_POOL_ID \
     --policies "PasswordPolicy={MinimumLength=8,RequireUppercase=true,RequireLowercase=true,RequireNumbers=true,TemporaryPasswordValidityDays=7}" \
     --region us-east-1
   ```

## Cost Considerations

- Cognito: First 50,000 MAUs free, then $0.0055 per MAU
- ALB: ~$16/month + data transfer
- EKS: Cluster $0.10/hour (~$73/month) + EC2 nodes

## Next Steps

1. Configure custom domain for ALB (optional)
2. Set up CloudWatch alarms for application monitoring
3. Configure backup for Cognito user pool
4. Implement session timeout policies
