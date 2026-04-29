from flask import Flask, render_template, jsonify, request, Response, session
import boto3
from datetime import datetime, timedelta
import json
import time
import os
import pytz
from werkzeug.security import generate_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)

# Get region from environment or use default
region = os.environ.get('AWS_REGION', os.environ.get('AWS_DEFAULT_REGION', 'us-east-1'))
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
    try:
        bots = []
        
        # Try Lex V2 first
        try:
            response = lex_client.list_bots(maxResults=1000)
            
            for bot_summary in response.get('botSummaries', []):
                bot_id = bot_summary['botId']
                bot_name = bot_summary['botName']
                
                # Get bot aliases to find log groups
                try:
                    aliases_response = lex_client.list_bot_aliases(botId=bot_id, maxResults=1000)
                    
                    for alias in aliases_response.get('botAliasSummaries', []):
                        alias_id = alias['botAliasId']
                        alias_name = alias.get('botAliasName', alias_id)
                        
                        # Get alias details to find conversation log settings
                        try:
                            alias_details = lex_client.describe_bot_alias(botId=bot_id, botAliasId=alias_id)
                            conv_logs = alias_details.get('conversationLogSettings', {})
                            text_logs = conv_logs.get('textLogSettings', [])
                            
                            for log_setting in text_logs:
                                if log_setting.get('enabled'):
                                    # Extract log group from ARN (handles custom log groups)
                                    log_group_arn = log_setting.get('destination', {}).get('cloudWatch', {}).get('logGroupArn', '')
                                    if log_group_arn:
                                        # ARN format: arn:aws:logs:region:account:log-group:LOG_GROUP_NAME
                                        log_group = log_group_arn.split(':log-group:')[-1]
                                        bots.append({
                                            'botName': bot_name,
                                            'botId': bot_id,
                                            'aliasName': alias_name,
                                            'aliasId': alias_id,
                                            'logGroup': log_group
                                        })
                                        print(f"Found Lex bot: {bot_name} ({alias_name}) -> {log_group}")
                        except Exception as e:
                            print(f"Error getting alias details for {bot_name}/{alias_name}: {e}")
                            continue
                except Exception as e:
                    print(f"Error listing aliases for bot {bot_name}: {e}")
                    continue
                    
        except Exception as v2_error:
            print(f"Lex V2 API error: {v2_error}")
            # Fallback: get all log groups that match Lex pattern
            try:
                all_logs = logs_client.describe_log_groups(logGroupNamePrefix='/aws/lex/')
                for lg in all_logs.get('logGroups', []):
                    log_group_name = lg['logGroupName']
                    parts = log_group_name.split('/')
                    bot_display_name = parts[-1] if len(parts) > 3 else log_group_name
                    bots.append({
                        'botName': bot_display_name,
                        'botId': '',
                        'aliasName': 'CloudWatch',
                        'aliasId': '',
                        'logGroup': log_group_name
                    })
            except Exception as fallback_error:
                print(f"Fallback error: {fallback_error}")
        
        print(f"Total Lex bots found: {len(bots)}")
        return jsonify({'bots': bots})
    except Exception as e:
        print(f"Error in get_lex_bots: {e}")
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
    app.run(host='0.0.0.0', port=5000, debug=True)
