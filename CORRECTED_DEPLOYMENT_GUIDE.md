# CORRECTED Deployment Guide - Proper Order
## For: log-shipper-app.170928836252.realhandsonlabs.net

This guide has the CORRECT order to avoid the "secret not found" error.

---

## Phase 1: Prerequisites Setup

### 1.1 Set Variables
```bash
export CLUSTER_NAME=logs-viewer-cluster
export REGION=us-east-1
export ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
export BASE_DOMAIN=170928836252.realhandsonlabs.net
export APP_SUBDOMAIN=log-shipper-app
export FULL_DOMAIN="${APP_SUBDOMAIN}.${BASE_DOMAIN}"
export APP_URL="https://${FULL_DOMAIN}"

echo "Account ID: $ACCOUNT_ID"
echo "App URL: $APP_URL"
```

### 1.2 Check Certificate
```bash
# Get certificate ARN
export CERT_ARN=$(aws acm list-certificates \
  --region $REGION \
  --query "CertificateSummaryList[?DomainName=='*.170928836252.realhandsonlabs.net'].CertificateArn" \
  --output text)

echo "Certificate ARN: $CERT_ARN"

# If empty, request certificate first
if [ -z "$CERT_ARN" ]; then
  echo "ERROR: No certificate found. Request one first:"
  echo "aws acm request-certificate --domain-name '*.170928836252.realhandsonlabs.net' --validation-method DNS --region $REGION"
  exit 1
fi
```

---

## Phase 2: EKS Cluster Setup (Skip if exists)

### 2.1 Create EKS Cluster
```bash
eksctl create cluster \
  --name $CLUSTER_NAME \
  --region $REGION \
  --nodegroup-name standard-workers \
  --node-type t3.medium \
  --nodes 2 \
  --nodes-min 1 \
  --nodes-max 3 \
  --managed

# Verify
kubectl get nodes
```

### 2.2 Install AWS Load Balancer Controller
```bash
# Associate OIDC
eksctl utils associate-iam-oidc-provider \
  --region $REGION \
  --cluster $CLUSTER_NAME \
  --approve

# Download IAM policy
curl -o iam-policy.json https://raw.githubusercontent.com/kubernetes-sigs/aws-load-balancer-controller/v2.7.0/docs/install/iam_policy.json

# Create IAM policy
aws iam create-policy \
  --policy-name AWSLoadBalancerControllerIAMPolicy \
  --policy-document file://iam-policy.json

# Create service account
eksctl create iamserviceaccount \
  --cluster=$CLUSTER_NAME \
  --namespace=kube-system \
  --name=aws-load-balancer-controller \
  --attach-policy-arn=arn:aws:iam::${ACCOUNT_ID}:policy/AWSLoadBalancerControllerIAMPolicy \
  --override-existing-serviceaccounts \
  --region $REGION \
  --approve

# Install CRDs
kubectl apply -k "github.com/aws/eks-charts/stable/aws-load-balancer-controller/crds?ref=master"

# Install via Helm
helm repo add eks https://aws.github.io/eks-charts
helm repo update

helm install aws-load-balancer-controller eks/aws-load-balancer-controller \
  -n kube-system \
  --set clusterName=$CLUSTER_NAME \
  --set serviceAccount.create=false \
  --set serviceAccount.name=aws-load-balancer-controller \
  --set region=$REGION \
  --set vpcId=$(aws eks describe-cluster --name $CLUSTER_NAME --region $REGION --query "cluster.resourcesVpcConfig.vpcId" --output text)

# Verify
kubectl get deployment -n kube-system aws-load-balancer-controller
```

---

## Phase 3: IAM Role for CloudWatch

### 3.1 Create IAM Policy
```bash
cat > cloudwatch-logs-policy.json <<'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "logs:DescribeLogGroups",
        "logs:DescribeLogStreams",
        "logs:FilterLogEvents"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "lex:ListBots",
        "lex:ListBotAliases",
        "lex:DescribeBotAlias"
      ],
      "Resource": "*"
    }
  ]
}
EOF

aws iam create-policy \
  --policy-name CloudWatchLogsViewerPolicy \
  --policy-document file://cloudwatch-logs-policy.json
```

### 3.2 Create Service Account with IRSA
```bash
eksctl create iamserviceaccount \
  --name cloudwatch-logs-viewer-sa \
  --namespace default \
  --cluster $CLUSTER_NAME \
  --region $REGION \
  --attach-policy-arn arn:aws:iam::${ACCOUNT_ID}:policy/CloudWatchLogsViewerPolicy \
  --approve \
  --override-existing-serviceaccounts

# Verify
kubectl get sa cloudwatch-logs-viewer-sa -o yaml
```

---

## Phase 4: Cognito Setup

### 4.1 Create User Pool
```bash
aws cognito-idp create-user-pool \
  --pool-name logs-viewer-users \
  --auto-verified-attributes email \
  --policies "PasswordPolicy={MinimumLength=8,RequireUppercase=true,RequireLowercase=true,RequireNumbers=true,RequireSymbols=false}" \
  --username-attributes email \
  --region $REGION \
  --output json > user-pool.json

export USER_POOL_ID=$(cat user-pool.json | jq -r '.UserPool.Id')
echo "User Pool ID: $USER_POOL_ID"

# Save for later
echo $USER_POOL_ID > user-pool-id.txt
```

### 4.2 Create Cognito Domain
```bash
export COGNITO_DOMAIN_PREFIX=logs-viewer-$(date +%s)

aws cognito-idp create-user-pool-domain \
  --domain $COGNITO_DOMAIN_PREFIX \
  --user-pool-id $USER_POOL_ID \
  --region $REGION

export COGNITO_DOMAIN="${COGNITO_DOMAIN_PREFIX}.auth.${REGION}.amazoncognito.com"
echo "Cognito Domain: $COGNITO_DOMAIN"

# Save for later
echo $COGNITO_DOMAIN > cognito-domain.txt
```

---

## Phase 5: Build and Push Docker Image

### 5.1 Create ECR Repository
```bash
aws ecr create-repository \
  --repository-name log-shipper \
  --region $REGION

# Login to ECR
aws ecr get-login-password --region $REGION | \
  docker login --username AWS --password-stdin ${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com
```

### 5.2 Build and Push
```bash
cd d:/test-repo

# Build
docker build -t log-shipper .

# Tag
docker tag log-shipper:latest ${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/log-shipper:latest

# Push
docker push ${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/log-shipper:latest

echo "Image: ${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/log-shipper:latest"
```

---

## Phase 6: Deploy WITHOUT Authentication (Get ALB First)

### 6.1 Update Manifests
```bash
cd k8s

# Update 02-deployment-no-auth.yaml
sed -i "s|<ACCOUNT_ID>|${ACCOUNT_ID}|g" 02-deployment-no-auth.yaml

# Update 04-ingress.yaml
sed -i "s|<YOUR_CERT_ARN>|${CERT_ARN}|g" 04-ingress.yaml

# For Windows PowerShell:
# (Get-Content 02-deployment-no-auth.yaml) -replace '<ACCOUNT_ID>', $env:ACCOUNT_ID | Set-Content 02-deployment-no-auth.yaml
# (Get-Content 04-ingress.yaml) -replace '<YOUR_CERT_ARN>', $env:CERT_ARN | Set-Content 04-ingress.yaml
```

### 6.2 Deploy Initial Resources
```bash
# Deploy in order (ServiceAccount already created by eksctl)
kubectl apply -f 02-deployment-no-auth.yaml
kubectl apply -f 03-service.yaml
kubectl apply -f 04-ingress.yaml

# Check pods are running
kubectl get pods -l app=cloudwatch-logs-viewer

# Wait for pods to be ready
kubectl wait --for=condition=ready pod -l app=cloudwatch-logs-viewer --timeout=300s
```

### 6.3 Wait for ALB Creation
```bash
echo "Waiting for ALB creation (this takes 3-5 minutes)..."
kubectl get ingress cloudwatch-logs-viewer -w

# In another terminal, get ALB DNS when ready
export ALB_DNS=$(kubectl get ingress cloudwatch-logs-viewer -o jsonpath='{.status.loadBalancer.ingress[0].hostname}')

echo "ALB DNS: $ALB_DNS"

# Save for later
echo $ALB_DNS > alb-dns.txt
```

---

## Phase 7: DNS Configuration

### 7.1 Create Route53 Record
```bash
# Get hosted zone ID
export HOSTED_ZONE_ID=$(aws route53 list-hosted-zones-by-name \
  --dns-name realhandsonlabs.net \
  --query 'HostedZones[0].Id' \
  --output text | cut -d'/' -f3)

echo "Hosted Zone ID: $HOSTED_ZONE_ID"

# Get ALB Hosted Zone ID
export ALB_ZONE_ID=$(aws elbv2 describe-load-balancers \
  --region $REGION \
  --query "LoadBalancers[?DNSName=='${ALB_DNS}'].CanonicalHostedZoneId" \
  --output text)

echo "ALB Zone ID: $ALB_ZONE_ID"

# Create Route53 change batch
cat > route53-change.json <<EOF
{
  "Changes": [{
    "Action": "UPSERT",
    "ResourceRecordSet": {
      "Name": "${FULL_DOMAIN}",
      "Type": "A",
      "AliasTarget": {
        "HostedZoneId": "${ALB_ZONE_ID}",
        "DNSName": "${ALB_DNS}",
        "EvaluateTargetHealth": true
      }
    }
  }]
}
EOF

# Apply DNS change
aws route53 change-resource-record-sets \
  --hosted-zone-id $HOSTED_ZONE_ID \
  --change-batch file://route53-change.json

echo "DNS record created: ${FULL_DOMAIN} -> ${ALB_DNS}"

# Wait for DNS propagation
echo "Waiting for DNS propagation (60 seconds)..."
sleep 60

# Test DNS
nslookup ${FULL_DOMAIN}
```

### 7.2 Test Application (Without Auth)
```bash
# Test HTTPS
curl -I $APP_URL

# Should return 200 OK
echo "Test in browser: $APP_URL"
```

---

## Phase 8: Create Cognito App Client (Now that we have the URL)

### 8.1 Create App Client
```bash
aws cognito-idp create-user-pool-client \
  --user-pool-id $USER_POOL_ID \
  --client-name logs-viewer-client \
  --generate-secret \
  --callback-urls "${APP_URL}/callback" \
  --logout-urls "${APP_URL}" \
  --allowed-o-auth-flows code \
  --allowed-o-auth-scopes openid email profile \
  --allowed-o-auth-flows-user-pool-client \
  --supported-identity-providers COGNITO \
  --region $REGION \
  --output json > app-client.json

export CLIENT_ID=$(cat app-client.json | jq -r '.UserPoolClient.ClientId')
export CLIENT_SECRET=$(cat app-client.json | jq -r '.UserPoolClient.ClientSecret')

echo "Client ID: $CLIENT_ID"
echo "Client Secret: $CLIENT_SECRET"

# Save for later
echo $CLIENT_ID > client-id.txt
echo $CLIENT_SECRET > client-secret.txt
```

---

## Phase 9: Create Kubernetes Secret

### 9.1 Generate Secret Key
```bash
export SECRET_KEY=$(openssl rand -hex 32)
echo "Secret Key: $SECRET_KEY"
```

### 9.2 Create Secret
```bash
kubectl create secret generic cognito-secrets \
  --from-literal=COGNITO_DOMAIN=$COGNITO_DOMAIN \
  --from-literal=COGNITO_CLIENT_ID=$CLIENT_ID \
  --from-literal=COGNITO_CLIENT_SECRET=$CLIENT_SECRET \
  --from-literal=SECRET_KEY=$SECRET_KEY

# Verify secret created
kubectl get secret cognito-secrets
```

---

## Phase 10: Update Deployment with Authentication

### 10.1 Update Deployment Manifest
```bash
cd k8s

# Update 06-deployment-with-auth.yaml
sed -i "s|<ACCOUNT_ID>|${ACCOUNT_ID}|g" 06-deployment-with-auth.yaml

# For Windows PowerShell:
# (Get-Content 06-deployment-with-auth.yaml) -replace '<ACCOUNT_ID>', $env:ACCOUNT_ID | Set-Content 06-deployment-with-auth.yaml
```

### 10.2 Apply Updated Deployment
```bash
# This will replace the existing deployment
kubectl apply -f 06-deployment-with-auth.yaml

# Watch rollout
kubectl rollout status deployment/cloudwatch-logs-viewer

# Check pods are running
kubectl get pods -l app=cloudwatch-logs-viewer

# Check logs
kubectl logs -l app=cloudwatch-logs-viewer --tail=50
```

---

## Phase 11: Add Developers

### 11.1 Add First Developer
```bash
aws cognito-idp admin-create-user \
  --user-pool-id $USER_POOL_ID \
  --username developer1@company.com \
  --user-attributes Name=email_verified,Value=true \
  --desired-delivery-mediums EMAIL \
  --region $REGION

echo "Developer added. They will receive a temporary password via email."
```

### 11.2 Add Multiple Developers (Optional)
```bash
cat > developers.txt <<EOF
developer1@company.com
developer2@company.com
developer3@company.com
EOF

while read email; do
  echo "Adding: $email"
  aws cognito-idp admin-create-user \
    --user-pool-id $USER_POOL_ID \
    --username "$email" \
    --user-attributes Name=email,Value="$email" Name=email_verified,Value=true \
    --desired-delivery-mediums EMAIL \
    --region $REGION
  echo "✓ Added: $email"
done < developers.txt
```

---

## Phase 12: Final Verification

### 12.1 Check All Resources
```bash
# Check pods
kubectl get pods -l app=cloudwatch-logs-viewer

# Check service
kubectl get svc cloudwatch-logs-viewer

# Check ingress
kubectl get ingress cloudwatch-logs-viewer

# Check secret
kubectl get secret cognito-secrets

# Check logs
kubectl logs -l app=cloudwatch-logs-viewer --tail=100
```

### 12.2 Test Authentication Flow
```bash
echo ""
echo "=========================================="
echo "✅ Deployment Complete!"
echo "=========================================="
echo "Application URL: $APP_URL"
echo "Cognito Domain: https://$COGNITO_DOMAIN"
echo ""
echo "Test the application:"
echo "1. Open: $APP_URL"
echo "2. Should redirect to Cognito login"
echo "3. Login with developer credentials"
echo "4. Should redirect back to application"
echo "=========================================="
```

### 12.3 Test in Browser
1. Open: `https://log-shipper-app.170928836252.realhandsonlabs.net`
2. Should redirect to Cognito login page
3. Login with developer email and temporary password
4. Change password when prompted
5. Should redirect back to application
6. Verify you can see CloudWatch logs

---

## Summary of Deployment Order

```
✅ Phase 1: Prerequisites (variables, certificate)
✅ Phase 2: EKS Cluster + ALB Controller
✅ Phase 3: IAM Role for CloudWatch (IRSA)
✅ Phase 4: Cognito User Pool + Domain
✅ Phase 5: Build & Push Docker Image
✅ Phase 6: Deploy WITHOUT Auth (get ALB URL)
✅ Phase 7: Create Route53 DNS Record
✅ Phase 8: Create Cognito App Client (with callback URL)
✅ Phase 9: Create Kubernetes Secret
✅ Phase 10: Update Deployment WITH Auth
✅ Phase 11: Add Developers
✅ Phase 12: Verify Everything Works
```

---

## Kubernetes Manifests Order

```
01-serviceaccount.yaml       (Created by eksctl, not needed)
02-deployment-no-auth.yaml   (Deploy FIRST - no Cognito)
03-service.yaml              (Deploy SECOND)
04-ingress.yaml              (Deploy THIRD - creates ALB)
05-secret-template.yaml      (Template only, use kubectl create secret)
06-deployment-with-auth.yaml (Deploy LAST - after secret exists)
```

---

## Troubleshooting

### If pods fail with "secret not found":
```bash
# Check if secret exists
kubectl get secret cognito-secrets

# If not, create it
kubectl create secret generic cognito-secrets \
  --from-literal=COGNITO_DOMAIN=$COGNITO_DOMAIN \
  --from-literal=COGNITO_CLIENT_ID=$CLIENT_ID \
  --from-literal=COGNITO_CLIENT_SECRET=$CLIENT_SECRET \
  --from-literal=SECRET_KEY=$(openssl rand -hex 32)

# Restart deployment
kubectl rollout restart deployment/cloudwatch-logs-viewer
```

### If ALB not created:
```bash
# Check ALB controller logs
kubectl logs -n kube-system deployment/aws-load-balancer-controller

# Check ingress events
kubectl describe ingress cloudwatch-logs-viewer
```

### If DNS not resolving:
```bash
# Check Route53 record
aws route53 list-resource-record-sets \
  --hosted-zone-id $HOSTED_ZONE_ID \
  --query "ResourceRecordSets[?Name=='${FULL_DOMAIN}.']"

# Test DNS
dig ${FULL_DOMAIN}
nslookup ${FULL_DOMAIN}
```

---

## Quick Commands

```bash
# View logs
kubectl logs -l app=cloudwatch-logs-viewer -f

# Restart app
kubectl rollout restart deployment/cloudwatch-logs-viewer

# Scale app
kubectl scale deployment cloudwatch-logs-viewer --replicas=3

# Delete everything
kubectl delete -f k8s/06-deployment-with-auth.yaml
kubectl delete -f k8s/04-ingress.yaml
kubectl delete -f k8s/03-service.yaml
kubectl delete secret cognito-secrets
```

---

**This is the CORRECT order! Follow it step by step.** 🚀
