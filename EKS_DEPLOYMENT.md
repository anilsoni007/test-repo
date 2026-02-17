# EKS Deployment Guide - CloudWatch Logs Viewer

## Prerequisites
- EKS cluster running
- kubectl configured
- AWS CLI installed
- AWS Load Balancer Controller installed in EKS
- Docker installed locally

## Step 1: Build and Push Docker Image to ECR

```bash
# Set variables
export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
export AWS_REGION=us-east-1
export ECR_REPO=cloudwatch-logs-viewer

# Create ECR repository
aws ecr create-repository --repository-name $ECR_REPO --region $AWS_REGION

# Login to ECR
aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com

# Build Docker image
docker build -t $ECR_REPO .

# Tag image
docker tag $ECR_REPO:latest $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPO:latest

# Push to ECR
docker push $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPO:latest
```

## Step 2: Create IAM Role for Service Account (IRSA)

```bash
# Set variables
export CLUSTER_NAME=your-eks-cluster-name
export NAMESPACE=default
export SERVICE_ACCOUNT=cloudwatch-logs-viewer-sa

# Create IAM policy
aws iam create-policy \
  --policy-name CloudWatchLogsViewerPolicy \
  --policy-document file://k8s/iam-policy.json

# Create IAM role and associate with service account
eksctl create iamserviceaccount \
  --name $SERVICE_ACCOUNT \
  --namespace $NAMESPACE \
  --cluster $CLUSTER_NAME \
  --attach-policy-arn arn:aws:iam::$AWS_ACCOUNT_ID:policy/CloudWatchLogsViewerPolicy \
  --approve \
  --override-existing-serviceaccounts
```

**Alternative: Manual IAM Role Creation**

If you don't use eksctl, create the role manually:

```bash
# Get OIDC provider
export OIDC_PROVIDER=$(aws eks describe-cluster --name $CLUSTER_NAME --query "cluster.identity.oidc.issuer" --output text | sed -e "s/^https:\/\///")

# Create trust policy
cat > trust-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::$AWS_ACCOUNT_ID:oidc-provider/$OIDC_PROVIDER"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "$OIDC_PROVIDER:sub": "system:serviceaccount:$NAMESPACE:$SERVICE_ACCOUNT",
          "$OIDC_PROVIDER:aud": "sts.amazonaws.com"
        }
      }
    }
  ]
}
EOF

# Create IAM role
aws iam create-role \
  --role-name CloudWatchLogsViewerRole \
  --assume-role-policy-document file://trust-policy.json

# Attach policy to role
aws iam attach-role-policy \
  --role-name CloudWatchLogsViewerRole \
  --policy-arn arn:aws:iam::$AWS_ACCOUNT_ID:policy/CloudWatchLogsViewerPolicy
```

## Step 3: Update Kubernetes Manifests

Update the following placeholders in the manifest files:

**k8s/deployment.yaml:**
- Replace `<ACCOUNT_ID>` with your AWS account ID
- Replace `<REGION>` with your AWS region (e.g., us-east-1)

**k8s/serviceaccount.yaml:**
- Replace `<ACCOUNT_ID>` with your AWS account ID

Or use sed:

```bash
sed -i "s/<ACCOUNT_ID>/$AWS_ACCOUNT_ID/g" k8s/deployment.yaml k8s/serviceaccount.yaml
sed -i "s/<REGION>/$AWS_REGION/g" k8s/deployment.yaml
```

## Step 4: Deploy to EKS

```bash
# Apply all manifests
kubectl apply -f k8s/serviceaccount.yaml
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
kubectl apply -f k8s/ingress.yaml

# Check deployment status
kubectl get deployments
kubectl get pods
kubectl get svc
kubectl get ingress
```

## Step 5: Get ALB URL

```bash
# Wait for ALB to be provisioned (takes 2-3 minutes)
kubectl get ingress cloudwatch-logs-viewer -w

# Get ALB URL
export ALB_URL=$(kubectl get ingress cloudwatch-logs-viewer -o jsonpath='{.status.loadBalancer.ingress[0].hostname}')
echo "Application URL: http://$ALB_URL"
```

## Step 6: Access Application

Open browser and navigate to the ALB URL:
```
http://<alb-url>
```

## Verify Deployment

```bash
# Check pod logs
kubectl logs -l app=cloudwatch-logs-viewer

# Check pod status
kubectl describe pod -l app=cloudwatch-logs-viewer

# Test service
kubectl port-forward svc/cloudwatch-logs-viewer 8080:80
# Visit http://localhost:8080
```

## Troubleshooting

**Pods not starting:**
```bash
kubectl describe pod -l app=cloudwatch-logs-viewer
kubectl logs -l app=cloudwatch-logs-viewer
```

**IAM permissions error:**
```bash
# Verify service account annotation
kubectl describe sa cloudwatch-logs-viewer-sa

# Check pod has correct service account
kubectl get pod -l app=cloudwatch-logs-viewer -o yaml | grep serviceAccountName
```

**ALB not created:**
```bash
# Check AWS Load Balancer Controller logs
kubectl logs -n kube-system deployment/aws-load-balancer-controller

# Verify ingress class
kubectl get ingressclass
```

**Cannot access CloudWatch Logs:**
- Verify IAM role has correct permissions
- Check AWS region matches your log groups
- Verify IRSA is configured correctly

## Update Deployment

```bash
# Build and push new image
docker build -t $ECR_REPO .
docker tag $ECR_REPO:latest $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPO:latest
docker push $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPO:latest

# Restart deployment
kubectl rollout restart deployment/cloudwatch-logs-viewer

# Check rollout status
kubectl rollout status deployment/cloudwatch-logs-viewer
```

## Scale Deployment

```bash
# Scale to 3 replicas
kubectl scale deployment cloudwatch-logs-viewer --replicas=3

# Auto-scale (optional)
kubectl autoscale deployment cloudwatch-logs-viewer --min=2 --max=10 --cpu-percent=70
```

## Clean Up

```bash
kubectl delete -f k8s/
aws ecr delete-repository --repository-name $ECR_REPO --force
aws iam detach-role-policy --role-name CloudWatchLogsViewerRole --policy-arn arn:aws:iam::$AWS_ACCOUNT_ID:policy/CloudWatchLogsViewerPolicy
aws iam delete-role --role-name CloudWatchLogsViewerRole
aws iam delete-policy --policy-arn arn:aws:iam::$AWS_ACCOUNT_ID:policy/CloudWatchLogsViewerPolicy
```

## Optional: HTTPS with ACM Certificate

Update `k8s/ingress.yaml` to add HTTPS:

```yaml
metadata:
  annotations:
    alb.ingress.kubernetes.io/certificate-arn: arn:aws:acm:region:account-id:certificate/cert-id
    alb.ingress.kubernetes.io/listen-ports: '[{"HTTP": 80}, {"HTTPS": 443}]'
    alb.ingress.kubernetes.io/ssl-redirect: '443'
```

## Cost Optimization

- Use Fargate for serverless pods (no EC2 management)
- Set appropriate resource limits
- Use HPA for auto-scaling based on traffic
- Consider spot instances for worker nodes
