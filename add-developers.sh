#!/bin/bash

# Quick script to add developers to Cognito User Pool
# Usage: ./add-developers.sh <user-pool-id> <email1> <email2> ...

USER_POOL_ID=$1
REGION=${AWS_REGION:-us-east-1}

if [ -z "$USER_POOL_ID" ]; then
    echo "Usage: $0 <user-pool-id> <email1> <email2> ..."
    echo "Example: $0 us-east-1_ABC123 dev1@company.com dev2@company.com"
    exit 1
fi

shift

if [ $# -eq 0 ]; then
    echo "Error: Please provide at least one email address"
    exit 1
fi

echo "Adding developers to User Pool: $USER_POOL_ID"
echo "Region: $REGION"
echo ""

for email in "$@"; do
    echo "Adding: $email"
    aws cognito-idp admin-create-user \
        --user-pool-id "$USER_POOL_ID" \
        --username "$email" \
        --user-attributes Name=email,Value="$email" Name=email_verified,Value=true \
        --desired-delivery-mediums EMAIL \
        --region "$REGION" 2>&1
    
    if [ $? -eq 0 ]; then
        echo "✓ Successfully added: $email"
    else
        echo "✗ Failed to add: $email"
    fi
    echo ""
done

echo "Done! Developers will receive temporary passwords via email."
