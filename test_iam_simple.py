#!/usr/bin/env python3
import boto3

# Test IAM access
iam = boto3.client('iam')
try:
    users = iam.list_users()['Users']
    print(f"IAM users found: {[u['UserName'] for u in users]}")
    
    # Check if test user exists
    if any(u['UserName'] == 'test-drift-user' for u in users):
        print("✅ test-drift-user exists")
    else:
        print("❌ test-drift-user not found")
        
except Exception as e:
    print(f"❌ IAM access failed: {e}")