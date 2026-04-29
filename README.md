# AWS CloudWatch Logs Viewer

A web application for developers to access AWS CloudWatch logs without direct AWS console access.

## Features
- View logs from Lambda, Lex, Amazon Connect, and all CloudWatch log groups
- Filter by log group, log stream, and time range
- Real-time log viewing
- No AWS console access required for developers

## Deployment Options

### Option 1: AWS Elastic Beanstalk (Recommended)

1. Install AWS CLI and EB CLI:
```bash
pip install awsebcli
```

2. Initialize and deploy:
```bash
eb init -p docker aws-logs-viewer --region us-east-1
eb create logs-viewer-env
eb open
```

3. The URL will be automatically generated (e.g., `logs-viewer-env.us-east-1.elasticbeanstalk.com`)

### Option 2: AWS ECS Fargate

1. Build and push Docker image:
```bash
aws ecr create-repository --repository-name logs-viewer
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <account-id>.dkr.ecr.us-east-1.amazonaws.com
docker build -t logs-viewer .
docker tag logs-viewer:latest <account-id>.dkr.ecr.us-east-1.amazonaws.com/logs-viewer:latest
docker push <account-id>.dkr.ecr.us-east-1.amazonaws.com/logs-viewer:latest
```

2. Create ECS cluster and service via AWS Console or CLI

### Option 3: AWS App Runner (Easiest)

1. Push code to GitHub
2. Go to AWS App Runner console
3. Create service from source code
4. Connect GitHub repository
5. Deploy automatically

## IAM Permissions Required

Attach this policy to the EC2 instance role, ECS task role, or App Runner service role:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "logs:DescribeLogGroups",
        "logs:DescribeLogStreams",
        "logs:FilterLogEvents"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "lex:ListBots",
        "lex:ListBotAliases",
        "lex:DescribeBotAlias"
      ],
      "Resource": "*"
    }
  ]
}
```

## Local Testing

```bash
pip install -r requirements.txt
python app.py
```

Visit `http://localhost:5000`

## Security Considerations

- Deploy in private subnet with ALB for HTTPS
- Use AWS Cognito or IAM authentication for production
- Restrict IAM role to specific log groups if needed
- Enable VPC endpoints for CloudWatch Logs

## Usage

1. Share the application URL with your developers
2. Developers select the log group (e.g., `/aws/lambda/function-name`)
3. Optionally filter by log stream and time range
4. Click "Load Logs" to view

## Cost Optimization

- CloudWatch Logs API calls are charged per request
- Consider caching frequently accessed logs
- Set appropriate time ranges to minimize data transfer
