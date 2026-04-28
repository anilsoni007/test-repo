# EKS Deployment Guide - CloudWatch Logs Viewer

## Prerequisites
- EKS cluster running
- kubectl configured
- AWS CLI installed
- AWS Load Balancer Controller installed in EKS
- Docker installed locally
- jq installed (for JSON parsing)

## Step 1: Build and Push Docker Image to ECR

```bash
# Set variables
export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
export AWS_REGION=us-east-1
export ECR_REPO=cloudwatch-logs-viewer

# Create ECR repository
aws ecr create-repository --repository-name $ECR_REPO --region $AWS_REGION

# Login to ECR
aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com

# Build Docker image
docker build -t $ECR_REPO .

# Tag image
docker tag $ECR_REPO:latest $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPO:latest

# Push to ECR
docker push $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPO:latest
```

## Step 2: Create IAM Role for Service Account (IRSA)

```bash
# Set variables
export CLUSTER_NAME=your-eks-cluster-name
export NAMESPACE=default
export SERVICE_ACCOUNT=cloudwatch-logs-viewer-sa

# Create IAM policy
aws iam create-policy \
  --policy-name CloudWatchLogsViewerPolicy \
  --policy-document file://k8s/iam-policy.json

# Create IAM role and associate with service account
eksctl create iamserviceaccount \
  --name $SERVICE_ACCOUNT \
  --namespace $NAMESPACE \
  --cluster $CLUSTER_NAME \
  --attach-policy-arn arn:aws:iam::$AWS_ACCOUNT_ID:policy/CloudWatchLogsViewerPolicy \
  --approve \
  --override-existing-serviceaccounts
```

**Alternative: Manual IAM Role Creation**

If you don't use eksctl, create the role manually:

```bash
# Get OIDC provider
export OIDC_PROVIDER=$(aws eks describe-cluster --name $CLUSTER_NAME --query "cluster.identity.oidc.issuer" --output text | sed -e "s/^https:\/\///")

# Create trust policy
cat > trust-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::$AWS_ACCOUNT_ID:oidc-provider/$OIDC_PROVIDER"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "$OIDC_PROVIDER:sub": "system:serviceaccount:$NAMESPACE:$SERVICE_ACCOUNT",
          "$OIDC_PROVIDER:aud": "sts.amazonaws.com"
        }
      }
    }
  ]
}
EOF

# Create IAM role
aws iam create-role \
  --role-name CloudWatchLogsViewerRole \
  --assume-role-policy-document file://trust-policy.json

# Attach policy to role
aws iam attach-role-policy \
  --role-name CloudWatchLogsViewerRole \
  --policy-arn arn:aws:iam::$AWS_ACCOUNT_ID:policy/CloudWatchLogsViewerPolicy
```

## Step 3: Update Kubernetes Manifests

Update the following placeholders in `k8s/all-in-one.yaml`:
- Replace `<ACCOUNT_ID>` with your AWS account ID
- Replace `<REGION>` with your AWS region (e.g., us-east-1)
- Update the IAM role ARN in ServiceAccount annotation
- Update the ECR image URL

Or use sed:

```bash
sed -i "s/<ACCOUNT_ID>/$AWS_ACCOUNT_ID/g" k8s/all-in-one.yaml
sed -i "s/<REGION>/$AWS_REGION/g" k8s/all-in-one.yaml
```

## Step 4: Deploy to EKS (Without Authentication First)

```bash
# Apply manifests
kubectl apply -f k8s/all-in-one.yaml

# Check deployment status
kubectl get deployments
kubectl get pods
kubectl get svc
kubectl get ingress
```

## Step 5: Get ALB URL

```bash
# Wait for ALB to be provisioned (takes 2-3 minutes)
kubectl get ingress cloudwatch-logs-viewer -w

# Get ALB URL
export ALB_DNS=$(kubectl get ingress cloudwatch-logs-viewer -o jsonpath='{.status.loadBalancer.ingress[0].hostname}')
echo "ALB DNS: $ALB_DNS"
```

## Step 6: Test Basic Access (Optional)

At this point, you can test the application without authentication:
```
http://<alb-dns>
```

---

## Enable User Authentication with AWS Cognito

### Step 1: Set ACM Certificate ARN

**Option A: Use existing certificate**
```bash
# If you already have an ACM certificate, just set the ARN
export CERT_ARN=arn:aws:acm:us-east-1:123456789012:certificate/your-cert-id

# Verify certificate
aws acm describe-certificate --certificate-arn $CERT_ARN
```

**Option B: Request new certificate**
```bash
# Request certificate for your domain
export CERT_ARN=$(aws acm request-certificate \
  --domain-name logs.yourdomain.com \
  --validation-method DNS \
  --region $AWS_REGION \
  --query 'CertificateArn' --output text)

echo "Certificate ARN: $CERT_ARN"

# Validate certificate via DNS (add CNAME records shown in ACM console)
aws acm describe-certificate --certificate-arn $CERT_ARN

# Wait for certificate validation
aws acm wait certificate-validated --certificate-arn $CERT_ARN
```

### Step 2: Create Cognito User Pool

```bash
# Create user pool
export USER_POOL_ID=$(aws cognito-idp create-user-pool \
  --pool-name cloudwatch-logs-viewer-users \
  --auto-verified-attributes email \
  --policies "PasswordPolicy={MinimumLength=8,RequireUppercase=true,RequireLowercase=true,RequireNumbers=true}" \
  --query 'UserPool.Id' --output text)

echo "User Pool ID: $USER_POOL_ID"

# Get User Pool ARN
export USER_POOL_ARN=$(aws cognito-idp describe-user-pool \
  --user-pool-id $USER_POOL_ID \
  --query 'UserPool.Arn' --output text)

echo "User Pool ARN: $USER_POOL_ARN"
```

### Step 3: Create Cognito User Pool Domain

```bash
# Create domain (must be globally unique)
aws cognito-idp create-user-pool-domain \
  --domain cloudwatch-logs-viewer-$AWS_ACCOUNT_ID \
  --user-pool-id $USER_POOL_ID

echo "Cognito Domain: cloudwatch-logs-viewer-$AWS_ACCOUNT_ID"

# Verify domain creation
aws cognito-idp describe-user-pool-domain \
  --domain cloudwatch-logs-viewer-$AWS_ACCOUNT_ID
```

### Step 4: Set Your Custom Domain (If Using One)

```bash
# Set your custom domain that will be used to access the application
# This should match your DNS record pointing to the ALB
export CUSTOM_DOMAIN=logs.yourdomain.com

# If you're using the ALB DNS directly, use:
# export CUSTOM_DOMAIN=$ALB_DNS
```

### Step 5: Create Cognito App Client

```bash
# Create app client with callback URL using your custom domain
export APP_CLIENT=$(aws cognito-idp create-user-pool-client \
  --user-pool-id $USER_POOL_ID \
  --client-name cloudwatch-logs-viewer-client \
  --generate-secret \
  --allowed-o-auth-flows code \
  --allowed-o-auth-scopes openid \
  --callback-urls https://$CUSTOM_DOMAIN/oauth2/idpresponse \
  --allowed-o-auth-flows-user-pool-client \
  --supported-identity-providers COGNITO \
  --query 'UserPoolClient' --output json)

export CLIENT_ID=$(echo $APP_CLIENT | jq -r '.ClientId')
echo "Client ID: $CLIENT_ID"

# Verify app client configuration
aws cognito-idp describe-user-pool-client \
  --user-pool-id $USER_POOL_ID \
  --client-id $CLIENT_ID
```

### Step 6: Update Ingress with Cognito Authentication

Update the Ingress annotations in `k8s/all-in-one.yaml`:

```bash
# Backup original file
cp k8s/all-in-one.yaml k8s/all-in-one.yaml.backup

# Update the auth-idp-cognito annotation with actual values
# Note: Make sure the JSON is properly formatted with userPoolArn, userPoolClientId, and userPoolDomain keys
```

Manually edit `k8s/all-in-one.yaml` and update the Ingress section:

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: cloudwatch-logs-viewer
  namespace: default
  annotations:
    alb.ingress.kubernetes.io/scheme: internet-facing
    alb.ingress.kubernetes.io/target-type: ip
    alb.ingress.kubernetes.io/listen-ports: '[{"HTTP": 80}, {"HTTPS": 443}]'
    alb.ingress.kubernetes.io/ssl-redirect: '443'
    alb.ingress.kubernetes.io/certificate-arn: <YOUR_CERT_ARN>
    alb.ingress.kubernetes.io/healthcheck-path: /
    alb.ingress.kubernetes.io/healthcheck-interval-seconds: '15'
    alb.ingress.kubernetes.io/healthcheck-timeout-seconds: '5'
    alb.ingress.kubernetes.io/success-codes: '200'
    alb.ingress.kubernetes.io/tags: Environment=production,Application=cloudwatch-logs-viewer
    alb.ingress.kubernetes.io/auth-type: cognito
    alb.ingress.kubernetes.io/auth-idp-cognito: '{"userPoolArn":"<YOUR_USER_POOL_ARN>","userPoolClientId":"<YOUR_CLIENT_ID>","userPoolDomain":"cloudwatch-logs-viewer-<YOUR_ACCOUNT_ID>"}'
    alb.ingress.kubernetes.io/auth-on-unauthenticated-request: authenticate
    alb.ingress.kubernetes.io/auth-scope: openid
    alb.ingress.kubernetes.io/auth-session-cookie: AWSELBAuthSessionCookie
    alb.ingress.kubernetes.io/auth-session-timeout: '3600'
spec:
  ingressClassName: alb
  rules:
  - http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: cloudwatch-logs-viewer
            port:
              number: 80
```

Replace the placeholders:
- `<YOUR_CERT_ARN>` with your certificate ARN
- `<YOUR_USER_POOL_ARN>` with your User Pool ARN
- `<YOUR_CLIENT_ID>` with your Client ID
- `<YOUR_ACCOUNT_ID>` with your AWS Account ID

**IMPORTANT**: Ensure the `auth-idp-cognito` JSON has the correct format with keys: `userPoolArn`, `userPoolClientId`, and `userPoolDomain`.

### Step 7: Apply Updated Ingress

```bash
# Validate YAML syntax
kubectl apply -f k8s/all-in-one.yaml --dry-run=client

# Apply the changes
kubectl apply -f k8s/all-in-one.yaml

# Wait for ALB to update (2-3 minutes)
kubectl get ingress cloudwatch-logs-viewer -w

# Check ALB controller logs for any errors
kubectl logs -n kube-system deployment/aws-load-balancer-controller --tail=50
```

### Step 8: Create Users

```bash
# Create a user
aws cognito-idp admin-create-user \
  --user-pool-id $USER_POOL_ID \
  --username admin@example.com \
  --user-attributes Name=email,Value=admin@example.com Name=email_verified,Value=true \
  --temporary-password TempPass123! \
  --message-action SUPPRESS

# Set permanent password
aws cognito-idp admin-set-user-password \
  --user-pool-id $USER_POOL_ID \
  --username admin@example.com \
  --password SecurePass123! \
  --permanent

echo "User created: admin@example.com / SecurePass123!"
```

### Step 9: Configure DNS (If Using Custom Domain)

```bash
# Get ALB DNS
echo "ALB DNS: $ALB_DNS"

# Create a CNAME record in your DNS provider:
# logs.yourdomain.com -> <ALB_DNS>
```

### Step 10: Test Authentication

1. Clear browser cache/cookies or use incognito mode
2. Navigate to your custom domain: `https://logs.yourdomain.com`
3. You'll be redirected to Cognito login page
4. Enter credentials: `admin@example.com` / `SecurePass123!`
5. Upon success, you'll be redirected to the application

---

## Managing Users

```bash
# List all users
aws cognito-idp list-users --user-pool-id $USER_POOL_ID

# Create additional user
aws cognito-idp admin-create-user \
  --user-pool-id $USER_POOL_ID \
  --username developer@company.com \
  --user-attributes Name=email,Value=developer@company.com Name=email_verified,Value=true \
  --message-action SUPPRESS

aws cognito-idp admin-set-user-password \
  --user-pool-id $USER_POOL_ID \
  --username developer@company.com \
  --password DevPass123! \
  --permanent

# Delete user
aws cognito-idp admin-delete-user \
  --user-pool-id $USER_POOL_ID \
  --username developer@company.com

# Disable user
aws cognito-idp admin-disable-user \
  --user-pool-id $USER_POOL_ID \
  --username developer@company.com

# Enable user
aws cognito-idp admin-enable-user \
  --user-pool-id $USER_POOL_ID \
  --username developer@company.com

# Reset user password
aws cognito-idp admin-set-user-password \
  --user-pool-id $USER_POOL_ID \
  --username developer@company.com \
  --password NewPass123! \
  --permanent
```

---

## Troubleshooting

### Pods not starting
```bash
kubectl describe pod -l app=cloudwatch-logs-viewer
kubectl logs -l app=cloudwatch-logs-viewer
```

### IAM permissions error
```bash
# Verify service account annotation
kubectl describe sa cloudwatch-logs-viewer-sa

# Check pod has correct service account
kubectl get pod -l app=cloudwatch-logs-viewer -o yaml | grep serviceAccountName
```

### ALB not created
```bash
# Check AWS Load Balancer Controller logs
kubectl logs -n kube-system deployment/aws-load-balancer-controller --tail=100

# Verify ingress class
kubectl get ingressclass

# Check ingress details
kubectl describe ingress cloudwatch-logs-viewer
```

### Cognito redirect_mismatch error
```bash
# This means callback URL doesn't match your domain
# Check current callback URLs
aws cognito-idp describe-user-pool-client \
  --user-pool-id $USER_POOL_ID \
  --client-id $CLIENT_ID \
  --query 'UserPoolClient.CallbackURLs'

# Update callback URL to match your actual domain
aws cognito-idp update-user-pool-client \
  --user-pool-id $USER_POOL_ID \
  --client-id $CLIENT_ID \
  --callback-urls https://logs.yourdomain.com/oauth2/idpresponse \
  --allowed-o-auth-flows code \
  --allowed-o-auth-scopes openid \
  --allowed-o-auth-flows-user-pool-client \
  --supported-identity-providers COGNITO
```

### ALB Ingress Controller JSON parsing error
```bash
# This usually means the auth-idp-cognito annotation has invalid JSON
# Verify the annotation format:
kubectl get ingress cloudwatch-logs-viewer -o yaml | grep auth-idp-cognito

# The JSON must have these keys: userPoolArn, userPoolClientId, userPoolDomain
# Example: '{"userPoolArn":"arn:...","userPoolClientId":"abc123","userPoolDomain":"domain-name"}'
```

### Certificate issues
```bash
# Check certificate status
aws acm describe-certificate --certificate-arn $CERT_ARN

# Ensure certificate is in same region as ALB
# Certificate must be ISSUED status
```

### Cannot access CloudWatch Logs
- Verify IAM role has correct permissions
- Check AWS region matches your log groups
- Verify IRSA is configured correctly

---

## Update Deployment

```bash
# Build and push new image
docker build -t $ECR_REPO .
docker tag $ECR_REPO:latest $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPO:latest
docker push $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPO:latest

# Restart deployment
kubectl rollout restart deployment/cloudwatch-logs-viewer

# Check rollout status
kubectl rollout status deployment/cloudwatch-logs-viewer
```

## Scale Deployment

```bash
# Scale to 3 replicas
kubectl scale deployment cloudwatch-logs-viewer --replicas=3

# Auto-scale (optional)
kubectl autoscale deployment cloudwatch-logs-viewer --min=2 --max=10 --cpu-percent=70
```

## Clean Up

```bash
# Delete Kubernetes resources
kubectl delete -f k8s/all-in-one.yaml

# Delete Cognito resources
aws cognito-idp delete-user-pool-client --user-pool-id $USER_POOL_ID --client-id $CLIENT_ID
aws cognito-idp delete-user-pool-domain --domain cloudwatch-logs-viewer-$AWS_ACCOUNT_ID --user-pool-id $USER_POOL_ID
aws cognito-idp delete-user-pool --user-pool-id $USER_POOL_ID

# Delete ECR repository
aws ecr delete-repository --repository-name $ECR_REPO --force

# Delete IAM resources
aws iam detach-role-policy --role-name CloudWatchLogsViewerRole --policy-arn arn:aws:iam::$AWS_ACCOUNT_ID:policy/CloudWatchLogsViewerPolicy
aws iam delete-role --role-name CloudWatchLogsViewerRole
aws iam delete-policy --policy-arn arn:aws:iam::$AWS_ACCOUNT_ID:policy/CloudWatchLogsViewerPolicy
```

## Cost Optimization

- Use Fargate for serverless pods (no EC2 management)
- Set appropriate resource limits
- Use HPA for auto-scaling based on traffic
- Consider spot instances for worker nodes
- Cognito User Pool: First 50,000 MAUs free, then $0.0055 per MAU
- ALB: ~$16/month + $0.008 per LCU-hour
- ACM certificates are free

## Security Best Practices

1. **Use HTTPS only**: Enforce SSL redirect in ALB
2. **Restrict IAM permissions**: Only grant necessary CloudWatch Logs permissions
3. **Enable MFA**: Configure MFA for Cognito users (optional)
4. **Session timeout**: Set appropriate session timeout (default 1 hour)
5. **Network security**: Deploy in private subnets with ALB in public subnet
6. **Audit logging**: Enable CloudTrail for API calls
7. **Regular updates**: Keep container images and dependencies updated
