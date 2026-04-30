# Deployment Checklist
## CloudWatch Logs Viewer - log-shipper-app.170928836252.realhandsonlabs.net

Use this checklist to track your deployment progress.

---

## Pre-Deployment

### Prerequisites
- [ ] AWS Account with admin access
- [ ] AWS CLI installed (`aws --version`)
- [ ] AWS CLI configured (`aws sts get-caller-identity`)
- [ ] kubectl installed (`kubectl version --client`)
- [ ] Docker installed (`docker --version`)
- [ ] eksctl installed (`eksctl version`)
- [ ] helm installed (`helm version`)
- [ ] jq installed (`jq --version`)

### AWS Resources Check
- [ ] Certificate exists for `*.170928836252.realhandsonlabs.net` in ACM
- [ ] Route53 hosted zone for `realhandsonlabs.net` exists
- [ ] IAM permissions verified (EKS, ECR, Cognito, IAM, Route53)

---

## Phase 1: Infrastructure Setup

### EKS Cluster
- [ ] EKS cluster created or exists
- [ ] kubectl configured for cluster
- [ ] Nodes are running (`kubectl get nodes`)
- [ ] OIDC provider associated

### AWS Load Balancer Controller
- [ ] IAM policy created: `AWSLoadBalancerControllerIAMPolicy`
- [ ] Service account created: `aws-load-balancer-controller`
- [ ] CRDs installed
- [ ] Helm chart installed
- [ ] Controller pods running (`kubectl get pods -n kube-system`)

### IAM Role for CloudWatch
- [ ] IAM policy created: `CloudWatchLogsViewerPolicy`
- [ ] Service account created: `cloudwatch-logs-viewer-sa`
- [ ] IRSA configured
- [ ] Role ARN noted

---

## Phase 2: Cognito Setup

### User Pool
- [ ] Cognito User Pool created
- [ ] User Pool ID saved: `_________________`
- [ ] Email verification enabled
- [ ] Password policy configured

### Cognito Domain
- [ ] Cognito domain created
- [ ] Domain name saved: `_________________`
- [ ] Full domain: `_________________.auth.us-east-1.amazoncognito.com`

---

## Phase 3: Application Deployment

### Docker Image
- [ ] ECR repository created: `cloudwatch-logs-viewer`
- [ ] Docker image built
- [ ] Image tagged
- [ ] Image pushed to ECR
- [ ] Image URI: `_________________`

### Kubernetes Manifest
- [ ] `all-in-one.yaml` updated with:
  - [ ] Account ID
  - [ ] Region
  - [ ] Certificate ARN
  - [ ] Image URI
  - [ ] Host: `log-shipper-app.170928836252.realhandsonlabs.net`
  - [ ] APP_URL: `https://log-shipper-app.170928836252.realhandsonlabs.net`

### Deploy to Kubernetes
- [ ] Manifest applied (`kubectl apply -f k8s/all-in-one.yaml`)
- [ ] ServiceAccount created
- [ ] Secret created (placeholder)
- [ ] Deployment created
- [ ] Service created
- [ ] Ingress created
- [ ] Pods running (`kubectl get pods`)

### ALB Creation
- [ ] ALB created (wait 3-5 minutes)
- [ ] Ingress has address (`kubectl get ingress`)
- [ ] ALB DNS name: `_________________`
- [ ] Health checks passing

---

## Phase 4: DNS Configuration

### Route53 Record
- [ ] Hosted Zone ID obtained
- [ ] ALB Hosted Zone ID obtained
- [ ] Route53 change batch created
- [ ] A record created: `log-shipper-app.170928836252.realhandsonlabs.net`
- [ ] DNS propagated (wait 1-5 minutes)
- [ ] DNS resolves correctly (`nslookup log-shipper-app.170928836252.realhandsonlabs.net`)

---

## Phase 5: Cognito Integration

### App Client
- [ ] Cognito App Client created
- [ ] Client ID saved: `_________________`
- [ ] Client Secret saved: `_________________`
- [ ] Callback URL: `https://log-shipper-app.170928836252.realhandsonlabs.net/callback`
- [ ] Logout URL: `https://log-shipper-app.170928836252.realhandsonlabs.net`
- [ ] OAuth flows configured

### Kubernetes Secrets
- [ ] Random SECRET_KEY generated
- [ ] Kubernetes secret `cognito-secrets` created/updated with:
  - [ ] COGNITO_DOMAIN
  - [ ] COGNITO_CLIENT_ID
  - [ ] COGNITO_CLIENT_SECRET
  - [ ] SECRET_KEY
- [ ] Deployment environment updated (APP_URL)
- [ ] Deployment restarted
- [ ] Pods restarted successfully

---

## Phase 6: User Management

### Add Developers
- [ ] First developer added
- [ ] Developer email: `_________________`
- [ ] Temporary password sent
- [ ] Additional developers added (if any)

### Test User Access
- [ ] User received email
- [ ] User can login
- [ ] User forced to change password
- [ ] User can access application

---

## Phase 7: Verification

### Application Access
- [ ] URL accessible: `https://log-shipper-app.170928836252.realhandsonlabs.net`
- [ ] HTTPS working (no certificate errors)
- [ ] Redirects to Cognito login
- [ ] Login successful
- [ ] Redirects back to application
- [ ] Application interface loads

### Functionality Testing
- [ ] Can list log groups
- [ ] Can select log group
- [ ] Can view log streams
- [ ] Can load logs
- [ ] Can filter by time range
- [ ] Can export logs (CSV)
- [ ] Logout works
- [ ] Re-login works

### Resource Verification
- [ ] All pods running (`kubectl get pods`)
- [ ] Service endpoints available (`kubectl get endpoints`)
- [ ] Ingress configured (`kubectl describe ingress`)
- [ ] ALB healthy (AWS Console)
- [ ] No errors in pod logs (`kubectl logs`)

---

## Phase 8: Post-Deployment

### Documentation
- [ ] Save all IDs and ARNs
- [ ] Document user pool ID
- [ ] Document client ID
- [ ] Document ALB DNS
- [ ] Create runbook for operations

### Monitoring Setup (Optional)
- [ ] CloudWatch alarms configured
- [ ] Log aggregation setup
- [ ] Metrics dashboard created
- [ ] Alerts configured

### Security Hardening (Optional)
- [ ] MFA enabled for Cognito
- [ ] Password expiration configured
- [ ] Session timeout configured
- [ ] IP restrictions (if needed)
- [ ] WAF rules (if needed)

### Backup & Recovery
- [ ] Kubernetes manifests in Git
- [ ] Cognito user pool backed up
- [ ] Recovery procedure documented
- [ ] Disaster recovery plan created

---

## Troubleshooting Checklist

If something doesn't work, check:

### ALB Issues
- [ ] ALB controller logs: `kubectl logs -n kube-system deployment/aws-load-balancer-controller`
- [ ] Ingress events: `kubectl describe ingress cloudwatch-logs-viewer`
- [ ] Security groups allow traffic
- [ ] Subnets are tagged correctly

### Pod Issues
- [ ] Pod status: `kubectl get pods -l app=cloudwatch-logs-viewer`
- [ ] Pod logs: `kubectl logs -l app=cloudwatch-logs-viewer`
- [ ] Pod events: `kubectl describe pod -l app=cloudwatch-logs-viewer`
- [ ] Image pull successful
- [ ] Environment variables set

### DNS Issues
- [ ] Route53 record exists
- [ ] DNS resolves: `nslookup log-shipper-app.170928836252.realhandsonlabs.net`
- [ ] Points to correct ALB
- [ ] DNS propagated globally

### Certificate Issues
- [ ] Certificate exists in ACM
- [ ] Certificate covers domain
- [ ] Certificate is validated
- [ ] Certificate in correct region

### Authentication Issues
- [ ] Cognito domain accessible
- [ ] App client configured correctly
- [ ] Callback URLs match exactly
- [ ] Secrets configured in Kubernetes
- [ ] Environment variables correct

### CloudWatch Access Issues
- [ ] IRSA configured correctly
- [ ] IAM policy has correct permissions
- [ ] Service account annotated with role ARN
- [ ] Pod using correct service account

---

## Success Criteria

✅ All items checked above  
✅ Application accessible at: `https://log-shipper-app.170928836252.realhandsonlabs.net`  
✅ Users can login with Cognito  
✅ Users can view CloudWatch logs  
✅ No errors in application logs  
✅ All pods healthy and running  

---

## Important Information to Save

```
AWS Account ID:        _________________
Region:                us-east-1
EKS Cluster Name:      _________________

Application URL:       https://log-shipper-app.170928836252.realhandsonlabs.net
ALB DNS:               _________________

Cognito User Pool ID:  _________________
Cognito Domain:        _________________
Cognito Client ID:     _________________
Cognito Client Secret: _________________ (keep secure!)

Certificate ARN:       _________________
Hosted Zone ID:        _________________

ECR Repository:        _________________
IAM Policy ARN:        _________________
IAM Role ARN (IRSA):   _________________
```

---

## Quick Commands Reference

```bash
# View pods
kubectl get pods -l app=cloudwatch-logs-viewer

# View logs
kubectl logs -l app=cloudwatch-logs-viewer -f

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

# List users
aws cognito-idp list-users --user-pool-id <USER_POOL_ID>

# Reset password
aws cognito-idp admin-reset-user-password \
  --user-pool-id <USER_POOL_ID> \
  --username user@company.com
```

---

## Deployment Date

Started: _______________  
Completed: _______________  
Deployed by: _______________

---

**Print this checklist and mark items as you complete them!**
