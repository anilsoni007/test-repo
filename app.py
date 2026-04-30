from flask import Flask, render_template, jsonify, request, Response, session, redirect, url_for, flash
import boto3
from datetime import datetime, timedelta
import json
import time
import os
import pytz
import logging
import sys
from functools import wraps
import psycopg2
from psycopg2.extras import RealDictCursor
from werkzeug.security import check_password_hash

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

# Database Configuration
DB_HOST = os.environ.get('DB_HOST')
DB_PORT = os.environ.get('DB_PORT', '5432')
DB_NAME = os.environ.get('DB_NAME', 'logsviewer')
DB_USER = os.environ.get('DB_USER')
DB_PASSWORD = os.environ.get('DB_PASSWORD')

# Get region from environment or use default
region = os.environ.get('AWS_REGION', os.environ.get('AWS_DEFAULT_REGION', 'us-east-1'))
logger.info(f"Initializing AWS clients for region: {region}")
logs_client = boto3.client('logs', region_name=region)
lex_client = boto3.client('lexv2-models', region_name=region)

# In-memory storage (use Redis/DynamoDB for production)
visitor_data = {'count': 0, 'date': datetime.now(pytz.timezone('Asia/Kolkata')).date().isoformat(), 'ips': set()}

def get_db_connection():
    """Get database connection"""
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            cursor_factory=RealDictCursor
        )
        return conn
    except Exception as e:
        logger.error(f"Database connection error: {e}")
        return None

def verify_user(email, password):
    """Verify user credentials"""
    conn = get_db_connection()
    if not conn:
        return None
    
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, email, name, is_active FROM users WHERE email = %s AND password_hash = crypt(%s, password_hash)",
                (email, password)
            )
            user = cur.fetchone()
            return user
    except Exception as e:
        logger.error(f"Error verifying user: {e}")
        return None
    finally:
        conn.close()

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        user = verify_user(email, password)
        
        if user and user['is_active']:
            session['user'] = {
                'id': user['id'],
                'email': user['email'],
                'name': user['name']
            }
            logger.info(f"User logged in: {email}")
            return redirect(url_for('index'))
        else:
            flash('Invalid email or password', 'error')
            return redirect(url_for('login'))
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user', None)
    flash('You have been logged out', 'info')
    return redirect(url_for('login'))

@app.route('/')
@login_required
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
    
    return render_template('index.html', user=session.get('user'))

@app.route('/api/stats')
@login_required
def get_stats():
    return jsonify({
        'visitors': visitor_data['count'],
        'date': visitor_data['date']
    })

@app.route('/api/log-groups')
@login_required
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
@login_required
def get_lex_bots():
    logger.info("=== Fetching Lex log groups ===")
    try:
        bots = []
        
        # Get all log groups under /aws/lex/ prefix
        logger.info("Fetching log groups with prefix /aws/lex/...")
        paginator = logs_client.get_paginator('describe_log_groups')
        
        for page in paginator.paginate(logGroupNamePrefix='/aws/lex/'):
            for log_group in page['logGroups']:
                log_group_name = log_group['logGroupName']
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
@login_required
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
@login_required
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
@login_required
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
    logger.info("Starting Flask application with native authentication...")
    app.run(host='0.0.0.0', port=5000, debug=True)
