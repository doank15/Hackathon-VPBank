# lambda_function_config_audit.py
import boto3
import json
import os
import datetime
import urllib.parse

sns = boto3.client("sns")
cloudtrail = boto3.client("cloudtrail")

def lambda_handler(event, context):
    detail = json.loads(event["Records"][0]["body"])["detail"]
    CI = detail.get("configurationItem", detail.get("configurationItemSummary"))
    if not CI:
        print("No config item found.")
        return

    resource_id = CI["resourceId"]
    resource_type = CI["resourceType"]
    capture_time = CI["configurationItemCaptureTime"]
    arn = CI.get("ARN")

    start_time = datetime.datetime.strptime(capture_time, '%Y-%m-%dT%H:%M:%S.%fZ') - datetime.timedelta(minutes=15)
    end_time = datetime.datetime.strptime(capture_time, '%Y-%m-%dT%H:%M:%S.%fZ')

    events = cloudtrail.lookup_events(
        LookupAttributes=[{
            "AttributeKey": "ResourceName",
            "AttributeValue": resource_id
        }],
        StartTime=start_time,
        EndTime=end_time,
        MaxResults=10
    ).get("Events", [])

    if not events:
        print(f"No CloudTrail events found for {resource_id}")
        return

    for evt in events:
        cloudtrail_event = json.loads(evt["CloudTrailEvent"])
        user_identity = cloudtrail_event.get("userIdentity", {})
        username = user_identity.get("arn", "unknown")
        message = {
            "resource_id": resource_id,
            "resource_type": resource_type,
            "event": evt["EventName"],
            "event_time": str(evt["EventTime"]),
            "user": username,
            "cloudtrail_event_id": evt["EventId"]
        }

        print("Detected config drift:\n", json.dumps(message, indent=2))
        notify(json.dumps(message, indent=2))

def notify(message):
    topic_arn = os.environ.get("SNSTopicARN")
    if topic_arn:
        sns.publish(
            TopicArn=topic_arn,
            Message=message,
            Subject="AWS Config Drift Detected"
        )
