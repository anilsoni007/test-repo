# import json
# import urllib3
# import os

# http = urllib3.PoolManager()

# def lambda_handler(event, context):
#     jenkins_url = os.environ['JENKINS_URL']
#     jenkins_token = os.environ['JENKINS_TOKEN']
    
#     # Forward GitHub webhook to Jenkins
#     headers = {
#         'Content-Type': 'application/json',
#         'X-GitHub-Event': event['headers'].get('X-GitHub-Event', ''),
#         'X-GitHub-Delivery': event['headers'].get('X-GitHub-Delivery', ''),
#         'Authorization': f'Bearer {jenkins_token}'
#     }
    
#     response = http.request(
#         'POST',
#         f'{jenkins_url}/github-webhook/',
#         body=event['body'],
#         headers=headers
#     )
    
#     return {
#         'statusCode': 200,
#         'body': json.dumps({'message': 'Webhook forwarded'})
#     }


# #     {
# #   "body": "{\"ref\":\"refs/heads/main\",\"repository\":{\"name\":\"test-repo\"}}",
# #   "headers": {
# #     "X-GitHub-Event": "push",
# #     "X-GitHub-Delivery": "test-123"
# #   }
# # }

import json
import urllib3
import os
import base64

http = urllib3.PoolManager()

def lambda_handler(event, context):
    try:
        # Jenkins configuration
        jenkins_url = os.environ['JENKINS_URL']
        jenkins_user = os.environ.get('JENKINS_USER', 'admin')
        jenkins_token = os.environ['JENKINS_TOKEN']
        
        # Define your Jenkins jobs here
        # Format: 'repo-name': ['job1', 'job2']
        JOB_MAPPINGS = {
            'your-repo-name': ['AL2023-Build-Job', 'Docker-Deploy-Job'],
            'another-repo': ['Another-Job']
        }
        
        # Parse GitHub webhook payload
        if isinstance(event.get('body'), str):
            payload = json.loads(event['body'])
        else:
            payload = event.get('body', {})
        
        # Extract repository name
        repo_name = payload.get('repository', {}).get('name', '')
        branch = payload.get('ref', '').replace('refs/heads/', '')
        
        print(f"Received webhook for repo: {repo_name}, branch: {branch}")
        
        # Get jobs to trigger
        jobs_to_trigger = JOB_MAPPINGS.get(repo_name, [])
        
        if not jobs_to_trigger:
            print(f"No jobs configured for repo: {repo_name}")
            return {
                'statusCode': 200,
                'body': json.dumps({'message': f'No jobs configured for {repo_name}'})
            }
        
        # Create Basic Auth header
        credentials = base64.b64encode(f'{jenkins_user}:{jenkins_token}'.encode()).decode()
        headers = {
            'Authorization': f'Basic {credentials}',
            'Content-Type': 'application/json'
        }
        
        results = []
        
        # Trigger each job
        for job_name in jobs_to_trigger:
            # Trigger with parameters (branch info)
            trigger_url = f'{jenkins_url}/job/{job_name}/buildWithParameters'
            
            # Build parameters
            params = {
                'BRANCH': branch,
                'TRIGGERED_BY': 'GitHub Webhook'
            }
            
            print(f"Triggering job: {job_name} with branch: {branch}")
            
            response = http.request(
                'POST',
                trigger_url,
                fields=params,
                headers=headers
            )
            
            result = {
                'job': job_name,
                'status': response.status,
                'success': response.status in [200, 201]
            }
            results.append(result)
            
            print(f"Job {job_name} trigger result: {response.status}")
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Jobs triggered',
                'repository': repo_name,
                'branch': branch,
                'results': results
            })
        }
        
    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }

