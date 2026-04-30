# AWS CloudWatch Logs Viewer

A web application for developers to access AWS CloudWatch logs without direct AWS console access.

## Features
- View logs from Lambda, Lex, Amazon Connect, and all CloudWatch log groups
- Filter by log group, log stream, and time range
- Real-time log viewing
- AWS Cognito authentication
- No AWS console access required for developers

---

## 🚀 Quick Start

### For EKS Deployment with Cognito (Recommended)

**Start here:** [START_HERE_CORRECTED.md](START_HERE_CORRECTED.md)

Then follow: [CORRECTED_DEPLOYMENT_GUIDE.md](CORRECTED_DEPLOYMENT_GUIDE.md)

---

## 📁 Documentation Structure

### Main Guides (Use These!)
1. **START_HERE_CORRECTED.md** - Overview and what to do
2. **CORRECTED_DEPLOYMENT_GUIDE.md** - Complete step-by-step deployment
3. **QUICK_FIX.md** - Quick reference card
4. **DEPLOYMENT_FLOW.md** - Visual flow diagrams

### Reference Guides
5. **DEPLOYMENT_CHECKLIST.md** - Track your deployment progress
6. **ARCHITECTURE.md** - System architecture and diagrams
7. **COGNITO_EKS_SETUP.md** - User management and security

### Alternative Deployments
8. **EC2_DEPLOYMENT.md** - Deploy on EC2
9. **EKS_DEPLOYMENT.md** - Generic EKS guide

---

## 📂 Kubernetes Manifests (k8s/)

Deploy in this order:

1. **02-deployment-no-auth.yaml** - Deploy FIRST (without Cognito)
2. **03-service.yaml** - Deploy SECOND
3. **04-ingress.yaml** - Deploy THIRD (creates ALB)
4. **06-deployment-with-auth.yaml** - Deploy LAST (with Cognito)

Templates (don't apply directly):
- **01-serviceaccount.yaml** - Created by eksctl
- **05-secret-template.yaml** - Use `kubectl create secret` instead

---

## 🎯 Deployment Overview

### Your Configuration
```
Application URL:  https://log-shipper-app.170928836252.realhandsonlabs.net
Cognito Domain:   logs-viewer-<timestamp>.auth.us-east-1.amazoncognito.com
ECR Repository:   <account-id>.dkr.ecr.us-east-1.amazonaws.com/log-shipper
```

### Deployment Steps
1. Setup EKS cluster and prerequisites
2. Create Cognito User Pool
3. Build and push Docker image
4. **Deploy WITHOUT authentication** (get ALB URL)
5. Create Route53 DNS record
6. Create Cognito App Client (with callback URL)
7. Create Kubernetes secret (with real values)
8. **Deploy WITH authentication**
9. Add developers to Cognito
10. ✅ Done!

---

## 🔐 Security Features

- HTTPS only (TLS 1.2+)
- AWS Cognito OAuth 2.0 authentication
- Email verification required
- IAM roles (IRSA) - no hardcoded credentials
- Session management (24-hour sessions)
- Strong password policies

---

## 💰 Cost Estimate

**~$150/month:**
- EKS Cluster: $73/month
- EC2 Nodes (2x t3.medium): $60/month
- Application Load Balancer: $16/month
- Cognito: FREE (first 50,000 users)
- Route53: $0.50/month

---

## 🛠️ Local Testing (Without Auth)

```bash
pip install -r requirements.txt
python app.py
```

Visit `http://localhost:5000`

---

## 📞 Quick Commands

```bash
# View pods
kubectl get pods -l app=cloudwatch-logs-viewer

# View logs
kubectl logs -l app=cloudwatch-logs-viewer -f

# Restart app
kubectl rollout restart deployment/cloudwatch-logs-viewer

# Add Cognito user
aws cognito-idp admin-create-user \
  --user-pool-id <USER_POOL_ID> \
  --username user@company.com \
  --user-attributes Name=email,Value=user@company.com Name=email_verified,Value=true \
  --desired-delivery-mediums EMAIL
```

---

## 🐛 Troubleshooting

See [QUICK_FIX.md](QUICK_FIX.md) for common issues and solutions.

---

## 📖 Full Documentation

For complete deployment instructions, see:
- [START_HERE_CORRECTED.md](START_HERE_CORRECTED.md)
- [CORRECTED_DEPLOYMENT_GUIDE.md](CORRECTED_DEPLOYMENT_GUIDE.md)
