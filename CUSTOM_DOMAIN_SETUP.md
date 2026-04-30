# Example: Using Existing Wildcard Domain with EKS

## Scenario: You have *.yourdomain.com wildcard certificate

### Step 1: Update all-in-one.yaml

```yaml
---
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: cloudwatch-logs-viewer
  namespace: default
  annotations:
    alb.ingress.kubernetes.io/scheme: internet-facing
    alb.ingress.kubernetes.io/target-type: ip
    alb.ingress.kubernetes.io/listen-ports: '[{"HTTPS": 443}]'
    # Use your existing wildcard certificate
    alb.ingress.kubernetes.io/certificate-arn: arn:aws:acm:us-east-1:<ACCOUNT>:certificate/<WILDCARD_CERT_ID>
    alb.ingress.kubernetes.io/ssl-redirect: '443'
    alb.ingress.kubernetes.io/healthcheck-path: /login
    alb.ingress.kubernetes.io/success-codes: '200,302'
spec:
  ingressClassName: alb
  rules:
  - host: logs.yourdomain.com  # Add this line
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: cloudwatch-logs-viewer
            port:
              number: 80
```

### Step 2: Update Deployment Environment

```yaml
env:
- name: APP_URL
  value: "https://logs.yourdomain.com"  # Your custom subdomain
```

### Step 3: Deploy and Get ALB URL

```bash
kubectl apply -f k8s/all-in-one.yaml

# Wait for ALB creation
kubectl get ingress cloudwatch-logs-viewer -w

# Get ALB DNS name
export ALB_DNS=$(kubectl get ingress cloudwatch-logs-viewer -o jsonpath='{.status.loadBalancer.ingress[0].hostname}')
echo $ALB_DNS
```

### Step 4: Create Route53 Record

**Option A: Using AWS CLI**
```bash
# Get your hosted zone ID
export ZONE_ID=$(aws route53 list-hosted-zones-by-name \
  --dns-name yourdomain.com \
  --query 'HostedZones[0].Id' \
  --output text | cut -d'/' -f3)

# Get ALB Hosted Zone ID (always same per region)
export ALB_ZONE_ID=$(aws elbv2 describe-load-balancers \
  --query "LoadBalancers[?DNSName=='$ALB_DNS'].CanonicalHostedZoneId" \
  --output text)

# Create A record (Alias)
cat > route53-change.json <<EOF
{
  "Changes": [{
    "Action": "UPSERT",
    "ResourceRecordSet": {
      "Name": "logs.yourdomain.com",
      "Type": "A",
      "AliasTarget": {
        "HostedZoneId": "$ALB_ZONE_ID",
        "DNSName": "$ALB_DNS",
        "EvaluateTargetHealth": true
      }
    }
  }]
}
EOF

aws route53 change-resource-record-sets \
  --hosted-zone-id $ZONE_ID \
  --change-batch file://route53-change.json
```

**Option B: Using AWS Console**
1. Go to Route53 → Hosted Zones → yourdomain.com
2. Create Record:
   - Record name: `logs`
   - Record type: `A`
   - Toggle "Alias" ON
   - Route traffic to: "Alias to Application Load Balancer"
   - Region: us-east-1
   - Select your ALB from dropdown
   - Click Create

### Step 5: Update Cognito Callback URLs

```bash
# Create Cognito domain (use AWS domain for simplicity)
aws cognito-idp create-user-pool-domain \
  --domain logs-viewer-$(date +%s) \
  --user-pool-id <USER_POOL_ID>

# Create app client with YOUR custom domain
aws cognito-idp create-user-pool-client \
  --user-pool-id <USER_POOL_ID> \
  --client-name logs-viewer-client \
  --generate-secret \
  --callback-urls "https://logs.yourdomain.com/callback" \
  --logout-urls "https://logs.yourdomain.com" \
  --allowed-o-auth-flows code \
  --allowed-o-auth-scopes openid email profile \
  --allowed-o-auth-flows-user-pool-client \
  --supported-identity-providers COGNITO
```

### Step 6: Update Kubernetes Secrets

```bash
kubectl create secret generic cognito-secrets \
  --from-literal=COGNITO_DOMAIN=<cognito-domain>.auth.us-east-1.amazoncognito.com \
  --from-literal=COGNITO_CLIENT_ID=<client-id> \
  --from-literal=COGNITO_CLIENT_SECRET=<client-secret> \
  --from-literal=SECRET_KEY=$(openssl rand -hex 32) \
  --dry-run=client -o yaml | kubectl apply -f -

# Update APP_URL
kubectl set env deployment/cloudwatch-logs-viewer APP_URL=https://logs.yourdomain.com

# Restart
kubectl rollout restart deployment/cloudwatch-logs-viewer
```

### Step 7: Test

```bash
# Wait for DNS propagation (1-5 minutes)
nslookup logs.yourdomain.com

# Test HTTPS
curl -I https://logs.yourdomain.com

# Access in browser
echo "Visit: https://logs.yourdomain.com"
```

## Summary

**Two Domains Involved:**

1. **Cognito Domain** (login page):
   - AWS Managed: `logs-viewer-xxx.auth.us-east-1.amazoncognito.com` ✅ Recommended
   - Custom: `auth.yourdomain.com` (requires separate ACM cert)

2. **Application Domain** (your app):
   - Use wildcard cert: `logs.yourdomain.com` ✅ You already have this
   - Just create Route53 A record pointing to ALB

**Recommendation:**
- Use **AWS Cognito domain** for login (free, easy)
- Use **your wildcard domain** for the app (logs.yourdomain.com)
- No need to create separate domain/certificate!
