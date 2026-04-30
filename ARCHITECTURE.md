# Architecture & Flow Diagram

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Internet / Users                             │
└────────────────────────────────┬────────────────────────────────────┘
                                 │
                                 │ HTTPS
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│                          Route53 DNS                                 │
│  log-shipper-app.170928836252.realhandsonlabs.net → ALB             │
└────────────────────────────────┬────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│                   Application Load Balancer (ALB)                    │
│  - HTTPS (Port 443)                                                  │
│  - SSL Certificate: *.170928836252.realhandsonlabs.net              │
│  - Health Check: /login                                              │
└────────────────────────────────┬────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         EKS Cluster                                  │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │                    Kubernetes Ingress                          │  │
│  │  - IngressClass: alb                                           │  │
│  │  - Host: log-shipper-app.170928836252.realhandsonlabs.net     │  │
│  └─────────────────────────────┬─────────────────────────────────┘  │
│                                │                                     │
│                                ▼                                     │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │              Kubernetes Service (NodePort)                     │  │
│  │  - Port: 80 → TargetPort: 5000                                │  │
│  └─────────────────────────────┬─────────────────────────────────┘  │
│                                │                                     │
│                                ▼                                     │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │                    Deployment (2 Pods)                         │  │
│  │  ┌─────────────────────┐    ┌─────────────────────┐           │  │
│  │  │   Pod 1             │    │   Pod 2             │           │  │
│  │  │  Flask App          │    │  Flask App          │           │  │
│  │  │  Port: 5000         │    │  Port: 5000         │           │  │
│  │  │  + Cognito Auth     │    │  + Cognito Auth     │           │  │
│  │  └─────────────────────┘    └─────────────────────┘           │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                                │                                     │
│                                │ Uses IRSA                           │
│                                ▼                                     │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │              Service Account (IRSA)                            │  │
│  │  cloudwatch-logs-viewer-sa                                     │  │
│  │  → IAM Role → CloudWatch Logs Permissions                     │  │
│  └───────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
                                 │
                                 │
        ┌────────────────────────┼────────────────────────┐
        │                        │                        │
        ▼                        ▼                        ▼
┌──────────────┐      ┌──────────────────┐      ┌──────────────┐
│   Cognito    │      │   CloudWatch     │      │  Secrets     │
│  User Pool   │      │      Logs        │      │  Manager     │
│              │      │                  │      │              │
│ - Users      │      │ - Log Groups     │      │ - Cognito    │
│ - Auth       │      │ - Log Streams    │      │   Secrets    │
│ - OAuth      │      │ - Events         │      │ - App Keys   │
└──────────────┘      └──────────────────┘      └──────────────┘
```

---

## Authentication Flow

```
1. User visits: https://log-shipper-app.170928836252.realhandsonlabs.net
   │
   ▼
2. Flask app checks session
   │
   ├─ No session? → Redirect to Cognito
   │                │
   │                ▼
   │   https://logs-viewer-xxx.auth.us-east-1.amazoncognito.com/login
   │                │
   │                ▼
   │   User enters email/password
   │                │
   │                ▼
   │   Cognito validates credentials
   │                │
   │                ▼
   │   Redirect to: https://log-shipper-app.170928836252.realhandsonlabs.net/callback
   │                │
   │                ▼
   │   Flask exchanges code for tokens
   │                │
   │                ▼
   │   Store user info in session
   │                │
   │                └──────────┐
   │                           │
   └─ Has session? ────────────┤
                               │
                               ▼
3. Show CloudWatch Logs Viewer Interface
   │
   ▼
4. User selects log group/stream
   │
   ▼
5. Flask app calls CloudWatch Logs API (using IRSA)
   │
   ▼
6. Display logs to user
```

---

## Data Flow

```
┌──────────┐
│  User    │
└────┬─────┘
     │
     │ 1. HTTPS Request
     ▼
┌─────────────────┐
│      ALB        │
└────┬────────────┘
     │
     │ 2. Forward to Pod
     ▼
┌─────────────────┐
│   Flask App     │
│   (Pod)         │
└────┬────────────┘
     │
     │ 3. Check Auth (Cognito)
     ▼
┌─────────────────┐
│   Cognito       │
│   User Pool     │
└────┬────────────┘
     │
     │ 4. Authenticated
     ▼
┌─────────────────┐
│   Flask App     │
│   (Pod)         │
└────┬────────────┘
     │
     │ 5. Query Logs (using IRSA)
     ▼
┌─────────────────┐
│  CloudWatch     │
│     Logs        │
└────┬────────────┘
     │
     │ 6. Return Log Data
     ▼
┌─────────────────┐
│   Flask App     │
│   (Pod)         │
└────┬────────────┘
     │
     │ 7. Render HTML
     ▼
┌─────────────────┐
│      ALB        │
└────┬────────────┘
     │
     │ 8. HTTPS Response
     ▼
┌──────────┐
│  User    │
└──────────┘
```

---

## Network Flow

```
Internet
   │
   │ Port 443 (HTTPS)
   ▼
┌─────────────────────────────────────┐
│         Public Subnet               │
│  ┌─────────────────────────────┐   │
│  │  Application Load Balancer  │   │
│  └──────────────┬──────────────┘   │
└─────────────────┼──────────────────┘
                  │
                  │ Port 80 → 5000
                  ▼
┌─────────────────────────────────────┐
│         Private Subnet              │
│  ┌─────────────────────────────┐   │
│  │      EKS Worker Nodes       │   │
│  │  ┌─────────┐  ┌─────────┐  │   │
│  │  │  Pod 1  │  │  Pod 2  │  │   │
│  │  └─────────┘  └─────────┘  │   │
│  └─────────────────────────────┘   │
└─────────────────────────────────────┘
                  │
                  │ HTTPS (via VPC Endpoints or NAT)
                  ▼
┌─────────────────────────────────────┐
│         AWS Services                │
│  - CloudWatch Logs                  │
│  - Cognito                          │
│  - ECR                              │
└─────────────────────────────────────┘
```

---

## Component Responsibilities

### 1. Route53
- DNS resolution
- Maps `log-shipper-app.170928836252.realhandsonlabs.net` to ALB

### 2. Application Load Balancer (ALB)
- SSL/TLS termination
- HTTPS enforcement
- Health checks
- Load balancing across pods

### 3. Kubernetes Ingress
- Routes traffic to service
- Manages ALB configuration
- Host-based routing

### 4. Kubernetes Service
- Service discovery
- Load balancing to pods
- Port mapping (80 → 5000)

### 5. Flask Application (Pods)
- Web interface
- Cognito OAuth integration
- CloudWatch Logs API calls
- Session management

### 6. Service Account (IRSA)
- IAM role for pods
- CloudWatch Logs permissions
- No hardcoded credentials

### 7. Cognito User Pool
- User authentication
- OAuth 2.0 provider
- User management
- Password policies

### 8. CloudWatch Logs
- Log storage
- Log retrieval
- Log filtering

### 9. Kubernetes Secrets
- Cognito credentials
- Application secrets
- Environment variables

---

## Security Layers

```
Layer 1: Network
├─ HTTPS only (TLS 1.2+)
├─ Private subnets for pods
└─ Security groups

Layer 2: Authentication
├─ AWS Cognito OAuth 2.0
├─ Email verification
├─ Strong password policy
└─ Session management

Layer 3: Authorization
├─ IAM roles (IRSA)
├─ Least privilege permissions
└─ No hardcoded credentials

Layer 4: Application
├─ Session cookies (HttpOnly, Secure)
├─ CSRF protection
└─ Input validation

Layer 5: Data
├─ Encrypted in transit (HTTPS)
├─ Encrypted at rest (EBS, S3)
└─ Secrets in Kubernetes Secrets
```

---

## Scaling Architecture

```
Horizontal Scaling (Pods):
┌─────────────────────────────────────┐
│  kubectl scale deployment           │
│  --replicas=5                        │
└─────────────────┬───────────────────┘
                  │
                  ▼
┌─────────────────────────────────────┐
│  ALB distributes traffic across:    │
│  ┌────┐ ┌────┐ ┌────┐ ┌────┐ ┌────┐│
│  │Pod1│ │Pod2│ │Pod3│ │Pod4│ │Pod5││
│  └────┘ └────┘ └────┘ └────┘ └────┘│
└─────────────────────────────────────┘

Vertical Scaling (Resources):
┌─────────────────────────────────────┐
│  Update deployment resources:       │
│  - CPU: 250m → 500m                 │
│  - Memory: 256Mi → 512Mi            │
└─────────────────────────────────────┘

Cluster Scaling (Nodes):
┌─────────────────────────────────────┐
│  EKS Cluster Autoscaler             │
│  - Min nodes: 1                     │
│  - Max nodes: 10                    │
│  - Auto-scale based on demand       │
└─────────────────────────────────────┘
```

---

## Monitoring & Logging

```
Application Logs:
kubectl logs -l app=cloudwatch-logs-viewer -f

Pod Metrics:
kubectl top pods -l app=cloudwatch-logs-viewer

Ingress Status:
kubectl describe ingress cloudwatch-logs-viewer

ALB Metrics (CloudWatch):
- RequestCount
- TargetResponseTime
- HTTPCode_Target_2XX_Count
- HTTPCode_Target_5XX_Count

EKS Metrics (CloudWatch):
- node_cpu_utilization
- node_memory_utilization
- pod_cpu_utilization
- pod_memory_utilization

Cognito Metrics (CloudWatch):
- UserAuthentication
- SignInSuccesses
- SignInThrottles
```

---

## Disaster Recovery

```
Backup Strategy:
1. Cognito User Pool
   - Export users regularly
   - Backup user pool configuration

2. Kubernetes Manifests
   - Version control (Git)
   - Backup all YAML files

3. Application Code
   - Git repository
   - ECR image tags

Recovery Steps:
1. Recreate EKS cluster
2. Restore Cognito user pool
3. Deploy from manifests
4. Update Route53 records
5. Verify functionality
```

---

## Cost Optimization

```
1. Right-size pods:
   - Monitor actual usage
   - Adjust CPU/memory requests

2. Use Spot instances:
   - For non-critical workloads
   - 70% cost savings

3. Enable cluster autoscaler:
   - Scale down during off-hours
   - Scale up during peak

4. Use Fargate (optional):
   - Pay per pod
   - No node management

5. Optimize ALB:
   - Use single ALB for multiple apps
   - Enable access logs only when needed
```

---

This architecture provides:
✅ High availability (multi-AZ)
✅ Scalability (horizontal & vertical)
✅ Security (multiple layers)
✅ Cost optimization
✅ Easy maintenance
