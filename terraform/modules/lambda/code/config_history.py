import json
import boto3
import os
from datetime import datetime, timedelta

def lambda_handler(event, context):
    """Get configuration history for a resource"""
    
    # Extract resource details from event
    resource_id = event.get('resourceId')
    resource_type = event.get('resourceType')
    
    if not resource_id or not resource_type:
        return {
            'statusCode': 400,
            'body': 'Missing resourceId or resourceType'
        }
    
    # Initialize AWS Config client
    config = boto3.client('config')
    cloudtrail = boto3.client('cloudtrail')
    
    try:
        # Get configuration history
        history = get_config_history(config, resource_type, resource_id)
        
        # Get CloudTrail events for the resource
        events = get_cloudtrail_events(cloudtrail, resource_id)
        
        # Correlate Config changes with CloudTrail events
        correlated_changes = correlate_changes(history, events)
        
        return {
            'statusCode': 200,
            'body': {
                'resource_id': resource_id,
                'resource_type': resource_type,
                'configuration_history': history,
                'cloudtrail_events': events,
                'correlated_changes': correlated_changes
            }
        }
    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            'statusCode': 500,
            'body': f"Error: {str(e)}"
        }

def get_config_history(config_client, resource_type, resource_id):
    """Get configuration history from AWS Config"""
    try:
        response = config_client.get_resource_config_history(
            resourceType=resource_type,
            resourceId=resource_id,
            limit=10  # Get last 10 configurations
        )
        
        history = []
        for item in response.get('configurationItems', []):
            history.append({
                'version': item.get('version'),
                'configurationItemStatus': item.get('configurationItemStatus'),
                'configurationStateId': item.get('configurationStateId'),
                'captureTime': item.get('captureTime').strftime('%Y-%m-%d %H:%M:%S') if item.get('captureTime') else None,
                'configuration': item.get('configuration')
            })
        
        return history
    except Exception as e:
        print(f"Error getting config history: {e}")
        return []

def get_cloudtrail_events(cloudtrail_client, resource_id):
    """Get CloudTrail events for a resource"""
    try:
        # Check events from the last 7 days
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(days=7)
        
        response = cloudtrail_client.lookup_events(
            LookupAttributes=[{
                'AttributeKey': 'ResourceName',
                'AttributeValue': resource_id
            }],
            StartTime=start_time,
            EndTime=end_time,
            MaxResults=10
        )
        
        events = []
        for event in response.get('Events', []):
            event_detail = json.loads(event.get('CloudTrailEvent', '{}'))
            events.append({
                'eventName': event.get('EventName'),
                'eventTime': event.get('EventTime').strftime('%Y-%m-%d %H:%M:%S') if event.get('EventTime') else None,
                'username': event.get('Username'),
                'resources': event.get('Resources'),
                'userIdentity': event_detail.get('userIdentity', {})
            })
        
        return events
    except Exception as e:
        print(f"Error getting CloudTrail events: {e}")
        return []

def correlate_changes(config_history, cloudtrail_events):
    """Correlate Config changes with CloudTrail events by timestamp"""
    correlated = []
    
    for config_item in config_history:
        config_time = config_item.get('captureTime')
        if not config_time:
            continue
        
        # Convert string back to datetime for comparison
        config_datetime = datetime.strptime(config_time, '%Y-%m-%d %H:%M:%S')
        
        # Find CloudTrail events within 5 minutes of the config change
        matching_events = []
        for event in cloudtrail_events:
            event_time = event.get('eventTime')
            if not event_time:
                continue
                
            event_datetime = datetime.strptime(event_time, '%Y-%m-%d %H:%M:%S')
            time_diff = abs((config_datetime - event_datetime).total_seconds())
            
            # If event is within 5 minutes of config change
            if time_diff <= 300:  # 5 minutes = 300 seconds
                matching_events.append(event)
        
        correlated.append({
            'config_item': config_item,
            'matching_events': matching_events
        })
    
    return correlated