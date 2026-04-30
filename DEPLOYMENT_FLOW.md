# Deployment Flow - Visual Guide

## ❌ WRONG Way (What You Experienced)

```
┌─────────────────────────────────────────────────────────────┐
│ Step 1: Deploy all-in-one.yaml                              │
│  - ServiceAccount                                            │
│  - Secret (with placeholder values)                          │
│  - Deployment (references secret)                            │
│  - Service                                                   │
│  - Ingress                                                   │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ Pod tries to start                                           │
│  - Looks for secret "cognito-secrets"                        │
│  - Secret exists but has placeholder values                  │
│  - Environment variables: COGNITO_DOMAIN=valueFrom...        │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ ❌ ERROR: Pod fails                                          │
│ "secret cognito-secrets not found" or                        │
│ "invalid Cognito configuration"                              │
└─────────────────────────────────────────────────────────────┘
```

---

## ✅ CORRECT Way (New Approach)

```
┌─────────────────────────────────────────────────────────────┐
│ Phase 1-5: Prerequisites                                     │
│  ✅ EKS Cluster                                              │
│  ✅ ALB Controller                                           │
│  ✅ IAM Role (IRSA)                                          │
│  ✅ Cognito User Pool + Domain                               │
│  ✅ Docker Image in ECR                                      │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ Phase 6: Deploy WITHOUT Authentication                       │
│  kubectl apply -f 02-deployment-no-auth.yaml                 │
│  kubectl apply -f 03-service.yaml                            │
│  kubectl apply -f 04-ingress.yaml                            │
│                                                              │
│  Deployment has NO Cognito environment variables             │
│  App runs without authentication (temporarily)               │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ ✅ Pods start successfully                                   │
│ ✅ Service created                                           │
│ ✅ Ingress created                                           │
│ ⏳ ALB creation in progress (3-5 minutes)                    │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ ✅ ALB Created!                                              │
│  ALB DNS: k8s-default-xxx.us-east-1.elb.amazonaws.com       │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ Phase 7: Create Route53 Record                              │
│  log-shipper-app.170928836252.realhandsonlabs.net → ALB     │
│                                                              │
│ ✅ Now you have the full URL!                                │
│  https://log-shipper-app.170928836252.realhandsonlabs.net   │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ Phase 8: Create Cognito App Client                          │
│  With callback URL:                                          │
│  https://log-shipper-app.170928836252...net/callback        │
│                                                              │
│ ✅ Get CLIENT_ID and CLIENT_SECRET                           │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ Phase 9: Create Kubernetes Secret                           │
│  kubectl create secret generic cognito-secrets \             │
│    --from-literal=COGNITO_DOMAIN=xxx \                       │
│    --from-literal=COGNITO_CLIENT_ID=xxx \                    │
│    --from-literal=COGNITO_CLIENT_SECRET=xxx \                │
│    --from-literal=SECRET_KEY=xxx                             │
│                                                              │
│ ✅ Secret created with REAL values                           │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ Phase 10: Update Deployment WITH Authentication             │
│  kubectl apply -f 06-deployment-with-auth.yaml               │
│                                                              │
│  Deployment now has Cognito environment variables            │
│  References the secret we just created                       │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ ✅ Pods restart successfully                                 │
│ ✅ Cognito authentication enabled                            │
│ ✅ Application fully functional                              │
└─────────────────────────────────────────────────────────────┘
```

---

## Side-by-Side Comparison

### Deployment Manifest Differences

#### 02-deployment-no-auth.yaml (Deploy FIRST)
```yaml
spec:
  containers:
  - name: cloudwatch-logs-viewer
    env:
    - name: AWS_REGION
      value: "us-east-1"
    # NO Cognito variables here!
    
    livenessProbe:
      httpGet:
        path: /              # ← Simple health check
        port: 5000
```

#### 06-deployment-with-auth.yaml (Deploy LAST)
```yaml
spec:
  containers:
  - name: cloudwatch-logs-viewer
    env:
    - name: AWS_REGION
      value: "us-east-1"
    - name: APP_URL
      value: "https://log-shipper-app.170928836252.realhandsonlabs.net"
    - name: COGNITO_DOMAIN
      valueFrom:
        secretKeyRef:
          name: cognito-secrets    # ← Secret must exist!
          key: COGNITO_DOMAIN
    - name: COGNITO_CLIENT_ID
      valueFrom:
        secretKeyRef:
          name: cognito-secrets
          key: COGNITO_CLIENT_ID
    - name: COGNITO_CLIENT_SECRET
      valueFrom:
        secretKeyRef:
          name: cognito-secrets
          key: COGNITO_CLIENT_SECRET
    - name: SECRET_KEY
      valueFrom:
        secretKeyRef:
          name: cognito-secrets
          key: SECRET_KEY
    
    livenessProbe:
      httpGet:
        path: /login         # ← Auth-aware health check
        port: 5000
```

---

## Timeline Visualization

```
Time    Action                              Result
────────────────────────────────────────────────────────────────
T+0     Deploy 02-deployment-no-auth.yaml   Pods start (no auth)
T+0     Deploy 03-service.yaml              Service created
T+0     Deploy 04-ingress.yaml              Ingress created
        
T+3min  ALB creation complete               ALB DNS available
        
T+4min  Create Route53 record               DNS configured
        
T+5min  Create Cognito App Client           CLIENT_ID obtained
        
T+6min  Create Kubernetes secret            Secret with real values
        
T+7min  Deploy 06-deployment-with-auth.yaml Pods restart with auth
        
T+8min  ✅ COMPLETE                          App fully functional
```

---

## Dependency Chain

```
EKS Cluster
    ↓
ALB Controller
    ↓
IRSA (Service Account)
    ↓
Cognito User Pool
    ↓
Cognito Domain
    ↓
Docker Image in ECR
    ↓
Deploy WITHOUT Auth ← START HERE
    ↓
ALB Created
    ↓
Route53 Record
    ↓
Full URL Available
    ↓
Cognito App Client ← Need URL for callback
    ↓
CLIENT_ID & CLIENT_SECRET
    ↓
Kubernetes Secret ← Need real values
    ↓
Deploy WITH Auth ← Secret must exist
    ↓
✅ SUCCESS
```

---

## What Each Phase Needs

### Phase 6 (Deploy WITHOUT Auth)
**Needs:**
- ✅ EKS cluster
- ✅ ALB controller
- ✅ Service account (IRSA)
- ✅ Docker image in ECR
- ✅ Certificate ARN

**Does NOT need:**
- ❌ Cognito App Client
- ❌ CLIENT_ID
- ❌ CLIENT_SECRET
- ❌ Kubernetes secret

### Phase 10 (Deploy WITH Auth)
**Needs:**
- ✅ Everything from Phase 6
- ✅ ALB DNS
- ✅ Route53 record
- ✅ Cognito App Client
- ✅ CLIENT_ID
- ✅ CLIENT_SECRET
- ✅ Kubernetes secret (with real values)

---

## File Usage Guide

```
┌─────────────────────────────────────────────────────────────┐
│ CORRECTED_DEPLOYMENT_GUIDE.md                                │
│ ↓                                                            │
│ Follow this step-by-step                                     │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ k8s/02-deployment-no-auth.yaml                               │
│ ↓                                                            │
│ kubectl apply -f 02-deployment-no-auth.yaml                  │
│ (Phase 6 - Deploy FIRST)                                     │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ k8s/03-service.yaml                                          │
│ ↓                                                            │
│ kubectl apply -f 03-service.yaml                             │
│ (Phase 6 - Deploy SECOND)                                    │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ k8s/04-ingress.yaml                                          │
│ ↓                                                            │
│ kubectl apply -f 04-ingress.yaml                             │
│ (Phase 6 - Deploy THIRD, creates ALB)                        │
└─────────────────────────────────────────────────────────────┘

        ⏳ Wait for ALB creation (3-5 minutes)
        ⏳ Create Route53 record
        ⏳ Create Cognito App Client
        ⏳ Create Kubernetes secret

┌─────────────────────────────────────────────────────────────┐
│ k8s/06-deployment-with-auth.yaml                             │
│ ↓                                                            │
│ kubectl apply -f 06-deployment-with-auth.yaml                │
│ (Phase 10 - Deploy LAST, after secret exists)                │
└─────────────────────────────────────────────────────────────┘
```

---

## Key Takeaways

1. **Deploy in TWO stages:**
   - Stage 1: Without auth (get ALB URL)
   - Stage 2: With auth (after secret exists)

2. **Secret must exist BEFORE deployment references it**

3. **You need the ALB URL BEFORE creating Cognito App Client**

4. **Cognito App Client needs the callback URL**

5. **Callback URL = https://your-domain.com/callback**

6. **Can't know the URL until ALB is created**

7. **Therefore: Deploy → Get URL → Create Client → Create Secret → Redeploy**

---

**Follow CORRECTED_DEPLOYMENT_GUIDE.md for success!** ✅
