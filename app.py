from flask import Flask, render_template, jsonify, request, Response, session
import boto3
from datetime import datetime, timedelta
import json
import time
import os
import pytz
import logging
import sys
from werkzeug.security import generate_password_hash

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)

# Get region from environment or use default
region = os.environ.get('AWS_REGION', os.environ.get('AWS_DEFAULT_REGION', 'us-east-1'))
logger.info(f"Initializing AWS clients for region: {region}")
logs_client = boto3.client('logs', region_name=region)
lex_client = boto3.client('lexv2-models', region_name=region)

# In-memory storage (use Redis/DynamoDB for production)
visitor_data = {'count': 0, 'date': datetime.now(pytz.timezone('Asia/Kolkata')).date().isoformat(), 'ips': set()}

@app.route('/')
def index():
    # Track visitor by IP
    ist = pytz.timezone('Asia/Kolkata')
    today = datetime.now(ist).date().isoformat()
    
    # Reset counter at midnight IST
    if visitor_data['date'] != today:
        visitor_data['count'] = 0
        visitor_data['date'] = today
        visitor_data['ips'] = set()
    
    # Get client IP
    client_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    if client_ip and client_ip not in visitor_data['ips']:
        visitor_data['count'] += 1
        visitor_data['ips'].add(client_ip)
    
    return render_template('index.html')

@app.route('/api/stats')
def get_stats():
    return jsonify({
        'visitors': visitor_data['count'],
        'date': visitor_data['date']
    })

@app.route('/api/log-groups')
def get_log_groups():
    try:
        log_groups = []
        paginator = logs_client.get_paginator('describe_log_groups')
        for page in paginator.paginate():
            log_groups.extend([lg['logGroupName'] for lg in page['logGroups']])
        return jsonify({'logGroups': sorted(log_groups)})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/lex-bots')
def get_lex_bots():
    logger.info("=== Fetching Lex log groups ===")
    try:
        bots = []
        
        # Get all log groups under /aws/lex/ prefix (same as Lambda approach)
        logger.info("Fetching log groups with prefix /aws/lex/...")
        paginator = logs_client.get_paginator('describe_log_groups')
        
        for page in paginator.paginate(logGroupNamePrefix='/aws/lex/'):
            for log_group in page['logGroups']:
                log_group_name = log_group['logGroupName']
                # Extract bot name from path: /aws/lex/abcd-bot -> abcd-bot
                bot_name = log_group_name.replace('/aws/lex/', '')
                
                bots.append({
                    'botName': bot_name,
                    'logGroup': log_group_name
                })
                logger.info(f"Found Lex bot log group: {bot_name} -> {log_group_name}")
        
        logger.info(f"=== Total Lex bot log groups found: {len(bots)} ===")
        return jsonify({'bots': bots})
    except Exception as e:
        logger.error(f"Error fetching Lex log groups: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({'error': str(e), 'bots': []}), 200

@app.route('/api/log-streams/<path:log_group>')
def get_log_streams(log_group):
    try:
        response = logs_client.describe_log_streams(
            logGroupName=log_group,
            orderBy='LastEventTime',
            descending=True,
            limit=50
        )
        streams = [s['logStreamName'] for s in response['logStreams']]
        return jsonify({'logStreams': streams})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/logs')
def get_logs():
    log_group = request.args.get('logGroup')
    log_stream = request.args.get('logStream')
    hours = int(request.args.get('hours', 1))
    export_format = request.args.get('format', 'json')
    
    try:
        start_time = int((datetime.now() - timedelta(hours=hours)).timestamp() * 1000)
        
        kwargs = {
            'logGroupName': log_group,
            'startTime': start_time,
            'limit': 1000
        }
        if log_stream:
            kwargs['logStreamNames'] = [log_stream]
        
        events = []
        response = logs_client.filter_log_events(**kwargs)
        events.extend(response['events'])
        
        while 'nextToken' in response and len(events) < 5000:
            kwargs['nextToken'] = response['nextToken']
            response = logs_client.filter_log_events(**kwargs)
            events.extend(response['events'])
        
        # Handle export formats
        if export_format == 'csv':
            import csv
            from io import StringIO
            output = StringIO()
            writer = csv.writer(output)
            writer.writerow(['Timestamp', 'Log Stream', 'Message'])
            for event in events:
                writer.writerow([
                    datetime.fromtimestamp(event['timestamp']/1000).strftime('%Y-%m-%d %H:%M:%S'),
                    event.get('logStreamName', ''),
                    event['message']
                ])
            return Response(output.getvalue(), mimetype='text/csv', 
                          headers={'Content-Disposition': f'attachment; filename=logs_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'})
        
        return jsonify({'events': events})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/stream-logs')
def stream_logs():
    log_group = request.args.get('logGroup')
    log_stream = request.args.get('logStream')
    
    def generate():
        try:
            start_time = int((datetime.now() - timedelta(minutes=5)).timestamp() * 1000)
            next_token = None
            
            while True:
                kwargs = {
                    'logGroupName': log_group,
                    'startTime': start_time,
                    'limit': 100
                }
                if log_stream:
                    kwargs['logStreamNames'] = [log_stream]
                if next_token:
                    kwargs['nextToken'] = next_token
                
                response = logs_client.filter_log_events(**kwargs)
                
                for event in response['events']:
                    yield f"data: {json.dumps(event)}\n\n"
                
                next_token = response.get('nextToken')
                if not next_token:
                    start_time = int(datetime.now().timestamp() * 1000)
                    time.sleep(2)
                    
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
    
    return Response(generate(), mimetype='text/event-stream')

if __name__ == '__main__':
    logger.info("Starting Flask application...")
    app.run(host='0.0.0.0', port=5000, debug=True)
