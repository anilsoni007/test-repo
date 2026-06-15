import json
import urllib3
import os

http = urllib3.PoolManager()

def lambda_handler(event, context):
    jenkins_url = os.environ['JENKINS_URL']
    jenkins_token = os.environ['JENKINS_TOKEN']
    
    # Forward GitHub webhook to Jenkins
    headers = {
        'Content-Type': 'application/json',
        'X-GitHub-Event': event['headers'].get('X-GitHub-Event', ''),
        'X-GitHub-Delivery': event['headers'].get('X-GitHub-Delivery', ''),
        'Authorization': f'Bearer {jenkins_token}'
    }
    
    response = http.request(
        'POST',
        f'{jenkins_url}/github-webhook/',
        body=event['body'],
        headers=headers
    )
    
    return {
        'statusCode': 200,
        'body': json.dumps({'message': 'Webhook forwarded'})
    }


#     {
#   "body": "{\"ref\":\"refs/heads/main\",\"repository\":{\"name\":\"test-repo\"}}",
#   "headers": {
#     "X-GitHub-Event": "push",
#     "X-GitHub-Delivery": "test-123"
#   }
# }
