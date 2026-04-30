# Quick Reference - Corrected Deployment Order

## The Problem You Had
```
❌ Pod tried to start → Looking for cognito-secrets → Secret doesn't exist → Pod fails
```

## The Solution
```
✅ Deploy WITHOUT auth → Get ALB URL → Create Cognito client → Create secret → Deploy WITH auth
```

---

## Correct Deployment Order (12 Steps)

### 1. Setup Variables
```bash
export ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
export REGION=us-east-1
export CLUSTER_NAME=logs-viewer-cluster
export APP_URL="https://log-shipper-app.170928836252.realhandsonlabs.net"
```

### 2. Create EKS Cluster (if needed)
```bash
eksctl create cluster --name $CLUSTER_NAME --region $REGION
```

### 3. Install ALB Controller
```bash
# See CORRECTED_DEPLOYMENT_GUIDE.md Phase 2.2
```

### 4. Create IAM Role (IRSA)
```bash
eksctl create iamserviceaccount \
  --name cloudwatch-logs-viewer-sa \
  --cluster $CLUSTER_NAME \
  --attach-policy-arn arn:aws:iam::${ACCOUNT_ID}:policy/CloudWatchLogsViewerPolicy \
  --approve
```

### 5. Create Cognito User Pool
```bash
aws cognito-idp create-user-pool --pool-name logs-viewer-users --output json > user-pool.json
export USER_POOL_ID=$(cat user-pool.json | jq -r '.UserPool.Id')
```

### 6. Create Cognito Domain
```bash
aws cognito-idp create-user-pool-domain --domain logs-viewer-$(date +%s) --user-pool-id $USER_POOL_ID
export COGNITO_DOMAIN="logs-viewer-xxx.auth.us-east-1.amazoncognito.com"
```

### 7. Build & Push Docker Image
```bash
docker build -t log-shipper .
docker tag log-shipper:latest ${ACCOUNT_ID}.dkr.ecr.us-east-1.amazonaws.com/log-shipper:latest
docker push ${ACCOUNT_ID}.dkr.ecr.us-east-1.amazonaws.com/log-shipper:latest
```

### 8. Deploy WITHOUT Authentication ⭐ KEY STEP
```bash
cd k8s
kubectl apply -f 02-deployment-no-auth.yaml
kubectl apply -f 03-service.yaml
kubectl apply -f 04-ingress.yaml

# Wait for ALB
kubectl get ingress cloudwatch-logs-viewer -w
export ALB_DNS=$(kubectl get ingress cloudwatch-logs-viewer -o jsonpath='{.status.loadBalancer.ingress[0].hostname}')
```

### 9. Create Route53 Record
```bash
# Create A record: log-shipper-app.170928836252.realhandsonlabs.net → ALB_DNS
# See CORRECTED_DEPLOYMENT_GUIDE.md Phase 7.1
```

### 10. Create Cognito App Client (NOW you have the URL!)
```bash
aws cognito-idp create-user-pool-client \
  --user-pool-id $USER_POOL_ID \
  --client-name logs-viewer-client \
  --generate-secret \
  --callback-urls "${APP_URL}/callback" \
  --logout-urls "${APP_URL}" \
  --output json > app-client.json

export CLIENT_ID=$(cat app-client.json | jq -r '.UserPoolClient.ClientId')
export CLIENT_SECRET=$(cat app-client.json | jq -r '.UserPoolClient.ClientSecret')
```

### 11. Create Kubernetes Secret (NOW you have all values!)
```bash
kubectl create secret generic cognito-secrets \
  --from-literal=COGNITO_DOMAIN=$COGNITO_DOMAIN \
  --from-literal=COGNITO_CLIENT_ID=$CLIENT_ID \
  --from-literal=COGNITO_CLIENT_SECRET=$CLIENT_SECRET \
  --from-literal=SECRET_KEY=$(openssl rand -hex 32)
```

### 12. Update Deployment WITH Authentication
```bash
kubectl apply -f 06-deployment-with-auth.yaml
kubectl rollout status deployment/cloudwatch-logs-viewer
```

---

## Kubernetes Manifests in Order

```
k8s/
├── 01-serviceaccount.yaml       ← Created by eksctl (skip)
├── 02-deployment-no-auth.yaml   ← Deploy FIRST (no Cognito vars)
├── 03-service.yaml              ← Deploy SECOND
├── 04-ingress.yaml              ← Deploy THIRD (creates ALB)
├── 05-secret-template.yaml      ← Template only (don't apply)
└── 06-deployment-with-auth.yaml ← Deploy LAST (after secret exists)
```

---

## Why This Order?

```
1. Deploy app without auth
   ↓
2. ALB gets created
   ↓
3. Get ALB DNS name
   ↓
4. Create Route53 record
   ↓
5. Now you have the full URL: https://log-shipper-app.170928836252.realhandsonlabs.net
   ↓
6. Create Cognito App Client with callback URL
   ↓
7. Get CLIENT_ID and CLIENT_SECRET
   ↓
8. Create Kubernetes secret with all values
   ↓
9. Update deployment to use the secret
   ↓
10. ✅ Pods start successfully!
```

---

## What Changed?

### Before (WRONG):
```yaml
# all-in-one.yaml had everything together
# Secret was empty placeholders
# Deployment tried to use secret immediately
# ❌ Pod fails: "secret cognito-secrets not found"
```

### After (CORRECT):
```yaml
# 02-deployment-no-auth.yaml - No Cognito vars
# Deploy this first, get ALB URL
# Create Cognito client with real URL
# Create secret with real values
# 06-deployment-with-auth.yaml - Has Cognito vars
# ✅ Pod starts successfully!
```

---

## Files to Use

### For Deployment:
1. **CORRECTED_DEPLOYMENT_GUIDE.md** ← Full step-by-step guide
2. **k8s/02-deployment-no-auth.yaml** ← Deploy first
3. **k8s/03-service.yaml** ← Deploy second
4. **k8s/04-ingress.yaml** ← Deploy third
5. **k8s/06-deployment-with-auth.yaml** ← Deploy last

### Don't Use:
- ❌ k8s/all-in-one.yaml (old, wrong order)
- ❌ k8s/all-in-one-ready.yaml (old, wrong order)
- ❌ QUICK_DEPLOY_YOUR_DOMAIN.md (old, wrong order)
- ❌ DEPLOYMENT_FOR_YOUR_DOMAIN.md (old, wrong order)

---

## Quick Fix for Your Current Issue

If you already have pods failing:

```bash
# 1. Delete the failing deployment
kubectl delete deployment cloudwatch-logs-viewer

# 2. Create the secret first
kubectl create secret generic cognito-secrets \
  --from-literal=COGNITO_DOMAIN="your-cognito-domain.auth.us-east-1.amazoncognito.com" \
  --from-literal=COGNITO_CLIENT_ID="your-client-id" \
  --from-literal=COGNITO_CLIENT_SECRET="your-client-secret" \
  --from-literal=SECRET_KEY=$(openssl rand -hex 32)

# 3. Deploy with auth
kubectl apply -f k8s/06-deployment-with-auth.yaml

# 4. Check pods
kubectl get pods -l app=cloudwatch-logs-viewer
```

---

## Verification Commands

```bash
# Check if secret exists
kubectl get secret cognito-secrets

# Check secret contents (base64 encoded)
kubectl get secret cognito-secrets -o yaml

# Check pods
kubectl get pods -l app=cloudwatch-logs-viewer

# Check pod logs
kubectl logs -l app=cloudwatch-logs-viewer

# Check pod events
kubectl describe pod -l app=cloudwatch-logs-viewer
```

---

## Success Criteria

✅ Pods are running
✅ No "secret not found" errors
✅ Application accessible at https://log-shipper-app.170928836252.realhandsonlabs.net
✅ Redirects to Cognito login
✅ Can login and view logs

---

**Follow CORRECTED_DEPLOYMENT_GUIDE.md for complete instructions!**
