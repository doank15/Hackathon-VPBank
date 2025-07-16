#!/usr/bin/env python3
import boto3

def check_iam_users():
    iam = boto3.client('iam')
    
    try:
        response = iam.list_users()
        users = response.get('Users', [])
        
        print(f"Found {len(users)} IAM users:")
        for user in users:
            print(f"- {user['UserName']} (ARN: {user['Arn']})")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_iam_users()