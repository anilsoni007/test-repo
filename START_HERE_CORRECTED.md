# ✅ CORRECTED Deployment Guide - READ THIS FIRST

## 🚨 Important: Previous Guides Were Wrong!

The original guides had the deployment order wrong, causing the error:
```
Error: secret "cognito-secrets" not found
```

**This has been FIXED!** Use the new guides below.

---

## 📁 Use These Files (CORRECTED)

### ✅ Main Guide
- **CORRECTED_DEPLOYMENT_GUIDE.md** ← Complete step-by-step guide

### ✅ Quick References
- **QUICK_FIX.md** ← Quick reference card
- **DEPLOYMENT_FLOW.md** ← Visual flow diagrams

### ✅ Kubernetes Manifests (in order)
1. `k8s/02-deployment-no-auth.yaml` ← Deploy FIRST
2. `k8s/03-service.yaml` ← Deploy SECOND
3. `k8s/04-ingress.yaml` ← Deploy THIRD
4. `k8s/06-deployment-with-auth.yaml` ← Deploy LAST

---

## ❌ Don't Use These Files (OLD/WRONG)

- ~~all-in-one.yaml~~ (wrong order)
- ~~all-in-one-ready.yaml~~ (wrong order)
- ~~QUICK_DEPLOY_YOUR_DOMAIN.md~~ (wrong order)
- ~~DEPLOYMENT_FOR_YOUR_DOMAIN.md~~ (wrong order)
- ~~QUICK_DEPLOY.md~~ (wrong order)
- ~~COMPLETE_DEPLOYMENT_GUIDE.md~~ (wrong order)

---

## 🎯 The Correct Deployment Order

```
1. Setup prerequisites (EKS, ALB Controller, IRSA, Cognito User Pool)
   ↓
2. Build and push Docker image
   ↓
3. Deploy WITHOUT authentication ⭐ KEY CHANGE
   kubectl apply -f k8s/02-deployment-no-auth.yaml
   kubectl apply -f k8s/03-service.yaml
   kubectl apply -f k8s/04-ingress.yaml
   ↓
4. Wait for ALB creation (3-5 minutes)
   ↓
5. Get ALB DNS name
   ↓
6. Create Route53 DNS record
   ↓
7. Create Cognito App Client (now you have the callback URL!)
   ↓
8. Get CLIENT_ID and CLIENT_SECRET
   ↓
9. Create Kubernetes secret (with real values!)
   kubectl create secret generic cognito-secrets ...
   ↓
10. Deploy WITH authentication
    kubectl apply -f k8s/06-deployment-with-auth.yaml
   ↓
11. ✅ SUCCESS - Pods start without errors!
```

---

## 🔑 Why This Order?

### The Problem:
- Cognito App Client needs a **callback URL**
- Callback URL = `https://log-shipper-app.170928836252.realhandsonlabs.net/callback`
- You don't know this URL until the ALB is created
- ALB is created when you deploy the Ingress
- Therefore: **Deploy first, get URL, then configure Cognito**

### The Solution:
1. Deploy app **without** Cognito authentication
2. Get the ALB URL
3. Create Cognito App Client with the correct callback URL
4. Create Kubernetes secret with real values
5. Update deployment **with** Cognito authentication

---

## 🚀 Quick Start (3 Commands)

```bash
# 1. Read the corrected guide
cat CORRECTED_DEPLOYMENT_GUIDE.md

# 2. Follow it step by step
# (It has all the commands ready to copy-paste)

# 3. Deploy in the correct order:
kubectl apply -f k8s/02-deployment-no-auth.yaml  # First
kubectl apply -f k8s/03-service.yaml             # Second
kubectl apply -f k8s/04-ingress.yaml             # Third
# ... wait for ALB, create Cognito client, create secret ...
kubectl apply -f k8s/06-deployment-with-auth.yaml # Last
```

---

## 📊 What Gets Deployed

### Your Configuration:
```
Application URL:  https://log-shipper-app.170928836252.realhandsonlabs.net
Cognito Domain:   logs-viewer-<timestamp>.auth.us-east-1.amazoncognito.com
ECR Repository:   <account-id>.dkr.ecr.us-east-1.amazonaws.com/log-shipper
```

### AWS Resources:
- ✅ EKS Cluster
- ✅ Application Load Balancer (HTTPS)
- ✅ Route53 A Record
- ✅ Cognito User Pool
- ✅ IAM Role (IRSA)
- ✅ ECR Repository

### Kubernetes Resources:
- ✅ ServiceAccount (cloudwatch-logs-viewer-sa)
- ✅ Deployment (2 replicas)
- ✅ Service (NodePort)
- ✅ Ingress (ALB)
- ✅ Secret (cognito-secrets)

---

## 📝 Kubernetes Manifests Explained

### 01-serviceaccount.yaml
- **Purpose:** Template only
- **Action:** Created by eksctl, don't apply manually

### 02-deployment-no-auth.yaml
- **Purpose:** Deploy app WITHOUT Cognito
- **When:** Phase 6 (FIRST deployment)
- **Why:** Get ALB URL before configuring Cognito

### 03-service.yaml
- **Purpose:** Kubernetes Service
- **When:** Phase 6 (with deployment)
- **Why:** Expose pods to Ingress

### 04-ingress.yaml
- **Purpose:** Create ALB
- **When:** Phase 6 (with deployment)
- **Why:** Get ALB DNS name

### 05-secret-template.yaml
- **Purpose:** Template only
- **Action:** Don't apply, use `kubectl create secret` instead

### 06-deployment-with-auth.yaml
- **Purpose:** Deploy app WITH Cognito
- **When:** Phase 10 (LAST deployment)
- **Why:** After secret exists with real values

---

## 🔐 Secret Creation

**Don't use the template file!** Create the secret with kubectl:

```bash
kubectl create secret generic cognito-secrets \
  --from-literal=COGNITO_DOMAIN="logs-viewer-xxx.auth.us-east-1.amazoncognito.com" \
  --from-literal=COGNITO_CLIENT_ID="your-client-id" \
  --from-literal=COGNITO_CLIENT_SECRET="your-client-secret" \
  --from-literal=SECRET_KEY=$(openssl rand -hex 32)
```

---

## ✅ Success Criteria

When everything is working:

1. ✅ Pods are running
   ```bash
   kubectl get pods -l app=cloudwatch-logs-viewer
   # Should show: Running
   ```

2. ✅ No errors in logs
   ```bash
   kubectl logs -l app=cloudwatch-logs-viewer
   # Should show: "Cognito authentication enabled"
   ```

3. ✅ Application accessible
   ```bash
   curl -I https://log-shipper-app.170928836252.realhandsonlabs.net
   # Should return: 302 (redirect to Cognito)
   ```

4. ✅ Can login via browser
   - Visit: https://log-shipper-app.170928836252.realhandsonlabs.net
   - Redirects to Cognito login
   - Login successful
   - Can view CloudWatch logs

---

## 🐛 Troubleshooting

### Error: "secret cognito-secrets not found"
**Cause:** Deployed 06-deployment-with-auth.yaml before creating the secret

**Fix:**
```bash
# Create the secret first
kubectl create secret generic cognito-secrets \
  --from-literal=COGNITO_DOMAIN=$COGNITO_DOMAIN \
  --from-literal=COGNITO_CLIENT_ID=$CLIENT_ID \
  --from-literal=COGNITO_CLIENT_SECRET=$CLIENT_SECRET \
  --from-literal=SECRET_KEY=$(openssl rand -hex 32)

# Restart deployment
kubectl rollout restart deployment/cloudwatch-logs-viewer
```

### Error: ALB not created
**Cause:** ALB controller not installed or misconfigured

**Fix:**
```bash
# Check ALB controller logs
kubectl logs -n kube-system deployment/aws-load-balancer-controller

# Check ingress events
kubectl describe ingress cloudwatch-logs-viewer
```

### Error: DNS not resolving
**Cause:** Route53 record not created or DNS not propagated

**Fix:**
```bash
# Check Route53 record exists
aws route53 list-resource-record-sets \
  --hosted-zone-id <ZONE_ID> \
  --query "ResourceRecordSets[?Name=='log-shipper-app.170928836252.realhandsonlabs.net.']"

# Wait for DNS propagation (up to 5 minutes)
nslookup log-shipper-app.170928836252.realhandsonlabs.net
```

---

## 📚 Documentation Structure

```
START_HERE_CORRECTED.md (this file)
    ↓
CORRECTED_DEPLOYMENT_GUIDE.md (complete guide)
    ↓
QUICK_FIX.md (quick reference)
    ↓
DEPLOYMENT_FLOW.md (visual diagrams)
```

---

## 💡 Key Differences from Old Guides

| Old (Wrong) | New (Correct) |
|-------------|---------------|
| Deploy all-in-one.yaml | Deploy in 2 stages |
| Secret with placeholders | Secret with real values |
| Pods fail immediately | Pods start successfully |
| Single deployment | Two deployments (no-auth → with-auth) |
| Need to fix after deployment | Works first time |

---

## 🎯 Next Steps

1. **Read:** CORRECTED_DEPLOYMENT_GUIDE.md
2. **Follow:** Step-by-step instructions
3. **Deploy:** In the correct order
4. **Verify:** Application works
5. **Add users:** Using Cognito commands

---

## 📞 Quick Commands

```bash
# View pods
kubectl get pods -l app=cloudwatch-logs-viewer

# View logs
kubectl logs -l app=cloudwatch-logs-viewer -f

# Check secret
kubectl get secret cognito-secrets

# Restart app
kubectl rollout restart deployment/cloudwatch-logs-viewer

# Check ingress
kubectl get ingress cloudwatch-logs-viewer

# Add user
aws cognito-idp admin-create-user \
  --user-pool-id <USER_POOL_ID> \
  --username user@company.com \
  --user-attributes Name=email,Value=user@company.com Name=email_verified,Value=true \
  --desired-delivery-mediums EMAIL
```

---

## 💰 Cost Estimate

**~$150/month:**
- EKS Cluster: $73/month
- EC2 Nodes (2x t3.medium): $60/month
- ALB: $16/month
- Cognito: FREE (first 50K users)
- Route53: $0.50/month

---

## ✅ Summary

**The fix:** Deploy without auth first, get ALB URL, then add auth.

**The guide:** CORRECTED_DEPLOYMENT_GUIDE.md

**The manifests:** 02, 03, 04 (first), then 06 (last)

**The result:** Working application with Cognito authentication!

---

**Start with CORRECTED_DEPLOYMENT_GUIDE.md now!** 🚀
