#!/usr/bin/env python3
import boto3
import json

def test_cloudtrail_regions():
    """Test CloudTrail access in multiple regions"""
    regions = ['ap-southeast-1', 'us-east-1']
    
    for region in regions:
        try:
            print(f"\n=== Testing CloudTrail in {region} ===")
            cloudtrail = boto3.client('cloudtrail', region_name=region)
            
            # Test basic access
            response = cloudtrail.lookup_events(MaxResults=5)
            events = response.get('Events', [])
            
            print(f"✅ Successfully connected to {region}")
            print(f"Found {len(events)} recent events")
            
            if events:
                latest = events[0]
                print(f"Latest event: {latest['EventName']} at {latest['EventTime']}")
                
        except Exception as e:
            print(f"❌ Failed to connect to {region}: {e}")

def test_iam_events():
    """Test finding IAM events in us-east-1"""
    try:
        print(f"\n=== Testing IAM Events in us-east-1 ===")
        cloudtrail = boto3.client('cloudtrail', region_name='us-east-1')
        
        # Look for IAM events
        response = cloudtrail.lookup_events(
            LookupAttributes=[{
                'AttributeKey': 'EventName',
                'AttributeValue': 'CreateUser'
            }],
            MaxResults=5
        )
        
        events = response.get('Events', [])
        print(f"Found {len(events)} CreateUser events")
        
        for event in events:
            event_detail = json.loads(event['CloudTrailEvent'])
            user_identity = event_detail.get('userIdentity', {})
            print(f"- {event['EventName']} by {user_identity.get('arn', 'unknown')} at {event['EventTime']}")
            
    except Exception as e:
        print(f"❌ Failed to search IAM events: {e}")

if __name__ == "__main__":
    test_cloudtrail_regions()
    test_iam_events()