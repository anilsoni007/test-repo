# test-repo

## EKS Cluster with Private Nodes

This Terraform configuration creates an EKS cluster (v1.31) with:
- Private node groups
- VPC CNI addon
- Kube-proxy addon
- CoreDNS addon
- Metrics Server (via Helm)

### Prerequisites
- AWS CLI configured
- Terraform >= 1.0
- kubectl

### Deploy
```bash
terraform init
terraform plan
terraform apply
```

### Configure kubectl
```bash
aws eks update-kubeconfig --region us-east-1 --name my-eks-cluster
```

### Verify addons
```bash
kubectl get pods -n kube-system
```
