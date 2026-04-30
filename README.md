# Native Authentication Branch

This branch implements **native login with RDS PostgreSQL** instead of AWS Cognito.

## What Changed

✅ **Removed:** AWS Cognito OAuth integration  
✅ **Added:** Native login page with email/password  
✅ **Added:** RDS PostgreSQL for user storage  
✅ **Added:** Database schema and user management scripts  

---

## Quick Start

### 1. Create RDS PostgreSQL Database
```bash
# See NATIVE_AUTH_GUIDE.md for detailed steps
aws rds create-db-instance --db-instance-identifier logs-viewer-db ...
```

### 2. Initialize Database
```bash
PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -U postgres -d logsviewer -f db/init.sql
```

### 3. Add Users
```bash
./db/add-user.sh "user@company.com" "User Name" "Password123!"
```

### 4. Deploy Application
```bash
# Create secret
kubectl create secret generic app-secrets \
  --from-literal=DB_HOST="your-rds-endpoint.rds.amazonaws.com" \
  --from-literal=DB_PASSWORD="YourPassword" \
  ...

# Deploy
kubectl apply -f k8s/07-deployment-native-auth.yaml
```

### 5. Login
Visit: `https://log-shipper-app.170928836252.realhandsonlabs.net`

---

## Files Added/Modified

### New Files:
- `templates/login.html` - Login page UI
- `db/init.sql` - Database schema
- `db/add-user.sh` - Script to add users
- `k8s/07-deployment-native-auth.yaml` - Deployment with RDS config
- `NATIVE_AUTH_GUIDE.md` - Complete deployment guide

### Modified Files:
- `app.py` - Native auth instead of Cognito
- `requirements.txt` - PostgreSQL driver instead of Authlib

---

## User Management

### Add User
```bash
./db/add-user.sh "email@company.com" "Full Name" "Password123!"
```

### List Users
```sql
SELECT email, name, is_active, created_at FROM users;
```

### Deactivate User
```sql
UPDATE users SET is_active = false WHERE email = 'user@company.com';
```

### Reset Password
```sql
UPDATE users SET password_hash = crypt('NewPassword123!', gen_salt('bf')) 
WHERE email = 'user@company.com';
```

---

## Benefits

✅ **Simpler** - No Cognito complexity  
✅ **Full Control** - Manage users directly in database  
✅ **Faster** - No external OAuth flow  
✅ **Cheaper** - No Cognito costs (though RDS adds ~$15/month)  
✅ **Flexible** - Easy to customize authentication logic  

---

## Documentation

- **NATIVE_AUTH_GUIDE.md** - Complete deployment guide
- **db/init.sql** - Database schema
- **db/add-user.sh** - User management script

---

## Switching Between Branches

### To use Cognito (main branch):
```bash
git checkout main
```

### To use Native Auth (this branch):
```bash
git checkout native_login
```

---

**Ready to deploy? Follow NATIVE_AUTH_GUIDE.md!**
