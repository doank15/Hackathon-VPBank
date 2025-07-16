import json
import boto3
import gzip
import io
import time

s3_client = boto3.client('s3')

# Set of CloudTrail event names relevant for drift detection
DRIFT_RELEVANT_EVENTS = {
    'PutRolePolicy', 'AttachUserPolicy', 'DetachUserPolicy', 'DeleteRolePolicy',
    'UpdateAssumeRolePolicy', 'CreateSecurityGroup', 'AuthorizeSecurityGroupIngress',
    'RevokeSecurityGroupIngress', 'DeleteSecurityGroup', 'UpdateSecurityGroupRuleDescriptionsIngress',
    'DeleteUser', 'CreateUser', 'DeleteRole', 'CreateRole', 'UpdateUser',
    'ModifyVpcAttribute', 'CreateVpc', 'DeleteVpc', 'RunInstances', 'TerminateInstances'
}

def lambda_handler(event, context):
    bucket_name = event.get('bucket_name')
    log_folder = event.get('log_folder')
    date = event.get('date')

    if not bucket_name or not log_folder or not date:
        return {
            'statusCode': 400,
            'error': 'Missing required parameters: bucket_name, log_folder, and date'
        }

    prefix = f"{log_folder}{date}"

    try:
        response = s3_client.list_objects_v2(Bucket=bucket_name, Prefix=prefix)
    except Exception as e:
        return {
            'statusCode': 500,
            'error': f"Error listing objects: {str(e)}"
        }

    if 'Contents' not in response:
        return {
            'statusCode': 404,
            'error': f'No log files found under prefix {prefix}'
        }

    all_events = []
    total_files = len(response['Contents'])
    total_events = 0
    total_processing_time = 0.0

    for obj in response['Contents']:
        object_key = obj['Key']

        start_time = time.time()

        try:
            s3_response = s3_client.get_object(Bucket=bucket_name, Key=object_key)
            with gzip.GzipFile(fileobj=io.BytesIO(s3_response['Body'].read()), mode='rb') as gz:
                log_data = json.load(gz)
        except Exception as e:
            # Log error and continue processing other files
            print(f"Error reading or parsing {object_key}: {e}")
            continue

        events = log_data.get('Records', [])
        num_events = len(events)
        total_events += num_events

        for event_record in events:
            event_name = event_record.get('eventName', 'N/A')
            event_time = event_record.get('eventTime', 'N/A')
            user_identity = event_record.get('userIdentity', {})
            user_arn = user_identity.get('arn', 'N/A')
            user_type = user_identity.get('type', 'N/A')
            source_ip = event_record.get('sourceIPAddress', 'N/A')
            event_source = event_record.get('eventSource', 'N/A')
            aws_region = event_record.get('awsRegion', 'N/A')
            event_status = event_record.get('errorCode', 'Success')

            resources = event_record.get('resources', [])
            resource_list = []
            for res in resources:
                resource_list.append({
                    'ARN': res.get('ARN', 'N/A'),
                    'ResourceType': res.get('resourceType', 'N/A')
                })

            event_info = {
                'EventName': event_name,
                'EventTime': event_time,
                'UserARN': user_arn,
                'UserType': user_type,
                'SourceIPAddress': source_ip,
                'EventSource': event_source,
                'AWSRegion': aws_region,
                'EventStatus': event_status,
                'Resources': resource_list,
                'IsDriftAlert': event_name in DRIFT_RELEVANT_EVENTS
            }

            all_events.append(event_info)

        elapsed = time.time() - start_time
        total_processing_time += elapsed

    return {
        'statusCode': 200,
        'filesProcessed': total_files,
        'eventsProcessed': total_events,
        'processingTimeSeconds': total_processing_time,
        'events': all_events
    }
