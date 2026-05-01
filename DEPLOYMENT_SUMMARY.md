# 🎉 Clean Native Authentication Setup

## Final Structure

```
d:\test-repo\
├── app.py                      # Flask app with native login
├── requirements.txt            # Dependencies (Flask, boto3, psycopg2)
├── Dockerfile                  # Container image
├── README.md                   # Main documentation
├── NATIVE_AUTH_GUIDE.md        # Deployment guide
├── ARCHITECTURE.md             # System architecture
│
├── templates/
│   ├── index.html             # Main logs viewer UI
│   └── login.html             # Login page
│
├── db/
│   ├── init.sql               # Database schema
│   └── add-user.sh            # Script to add users
│
└── k8s/
    ├── deployment.yaml        # Kubernetes deployment
    ├── service.yaml           # Kubernetes service
    ├── ingress.yaml           # ALB ingress (HTTPS + redirect)
    └── iam-policy.json        # CloudWatch IAM policy
```

---

## What You Have Now

✅ **Native Login** - Email/password authentication  
✅ **RDS PostgreSQL** - User storage with encrypted passwords  
✅ **Clean Codebase** - No Cognito complexity  
✅ **Simple Deployment** - 3 Kubernetes manifests  
✅ **User Management** - Easy SQL commands or bash script  
✅ **HTTPS** - Auto-redirect from HTTP  
✅ **Production Ready** - Health checks, resource limits  

---

## Quick Deployment

### 1. Create RDS Database
```bash
aws rds create-db-instance \
  --db-instance-identifier logs-viewer-db \
  --db-instance-class db.t3.micro \
  --engine postgres \
  --master-username postgres \
  --master-user-password 'YourPassword123!' \
  --allocated-storage 20 \
  --db-name logsviewer
```

### 2. Initialize Database
```bash
export DB_HOST="your-rds-endpoint.rds.amazonaws.com"
export DB_PASSWORD="YourPassword123!"

PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -U postgres -d logsviewer -f db/init.sql
```

### 3. Add Users
```bash
./db/add-user.sh "user@company.com" "User Name" "Password123!"
```

### 4. Deploy to Kubernetes
```bash
# Create secret
kubectl create secret generic app-secrets \
  --from-literal=SECRET_KEY=$(openssl rand -hex 32) \
  --from-literal=DB_HOST="$DB_HOST" \
  --from-literal=DB_PORT="5432" \
  --from-literal=DB_NAME="logsviewer" \
  --from-literal=DB_USER="postgres" \
  --from-literal=DB_PASSWORD="$DB_PASSWORD"

# Deploy
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
kubectl apply -f k8s/ingress.yaml
```

### 5. Access
Visit: `https://log-shipper-app.<ACCOUNT_ID>.realhandsonlabs.net`

---

## User Management

### Add User
```bash
./db/add-user.sh "email@company.com" "Full Name" "Password123!"
```

### List Users
```sql
SELECT email, name, is_active FROM users;
```

### Deactivate User
```sql
UPDATE users SET is_active = false WHERE email = 'user@company.com';
```

### Reset Password
```sql
UPDATE users SET password_hash = crypt('NewPass123!', gen_salt('bf')) 
WHERE email = 'user@company.com';
```

---

## Files Removed

❌ All Cognito-related files  
❌ Old deployment guides  
❌ Numbered manifest files  
❌ Cognito user scripts  

---

## Documentation

- **README.md** - Overview and quick start
- **NATIVE_AUTH_GUIDE.md** - Complete deployment guide
- **ARCHITECTURE.md** - System architecture

---

## Cost

**~$165/month:**
- EKS: $73/month
- EC2 (2x t3.medium): $60/month
- ALB: $16/month
- RDS (db.t3.micro): $15/month
- Route53: $0.50/month

---

## Next Steps

1. Follow **NATIVE_AUTH_GUIDE.md** for detailed deployment
2. Create RDS database
3. Add your users
4. Deploy and test!

**No more Cognito headaches! 🚀**
