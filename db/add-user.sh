#!/bin/bash
# Script to add users to the database

# Usage: ./add-user.sh email name password

if [ $# -ne 3 ]; then
    echo "Usage: $0 <email> <name> <password>"
    echo "Example: $0 user@company.com 'John Doe' 'SecurePass123'"
    exit 1
fi

EMAIL=$1
NAME=$2
PASSWORD=$3

# Database connection details from environment or defaults
DB_HOST=${DB_HOST:-localhost}
DB_PORT=${DB_PORT:-5432}
DB_NAME=${DB_NAME:-logsviewer}
DB_USER=${DB_USER:-postgres}

# Insert user
PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME <<EOF
INSERT INTO users (email, name, password_hash) 
VALUES ('$EMAIL', '$NAME', crypt('$PASSWORD', gen_salt('bf')))
ON CONFLICT (email) DO UPDATE 
SET name = EXCLUDED.name, 
    password_hash = EXCLUDED.password_hash,
    updated_at = CURRENT_TIMESTAMP;
EOF

if [ $? -eq 0 ]; then
    echo "✓ User added/updated successfully: $EMAIL"
else
    echo "✗ Failed to add user"
    exit 1
fi
