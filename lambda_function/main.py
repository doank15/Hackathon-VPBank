import json
import boto3
import os
from datetime import datetime, timedelta, timezone

cloudtrail = boto3.client("cloudtrail")
s3 = boto3.client("s3")

def lambda_handler(event, context):
    action = event.get("action")
    parameters = event.get("parameters", {})

    if action == "lookup_cloudtrail":
        return lookup_cloudtrail(parameters)
    elif action == "get_s3_object":
        return get_s3_object(parameters)
    elif action == "scan_new_resources":
        return scan_new_resources(parameters)
    else:
        return {"error": f"Unsupported action: {action}"}

def lookup_cloudtrail(params):
    resource_id = params.get("resource_id")
    if not resource_id:
        return {"error": "Missing resource_id"}

    try:
        # Get current UTC time and add 7 hours for UTC+7
        utc_plus_7 = timezone(timedelta(hours=7))
        end_time = datetime.now(utc_plus_7)
        start_time = end_time - timedelta(minutes=5)
        events = cloudtrail.lookup_events(
            LookupAttributes=[
                {"AttributeKey": "ResourceName", 
                 "AttributeValue": resource_id
                }
            ],
            StartTime=start_time,
            EndTime=end_time,
            # MaxResults=10
        )
        return {"events": events.get("Events", [])}
    except Exception as e:
        return {"error": str(e)}

def get_s3_object(params):
    bucket = params.get("bucket")
    key = params.get("key")
    if not bucket or not key:
        return {"error": "Missing bucket or key"}

    try:
        obj = s3.get_object(Bucket=bucket, Key=key)
        body = obj["Body"].read().decode("utf-8")
        return {"content": body}
    except Exception as e:
        return {"error": str(e)}

def scan_new_resources(params):
    start_str = params.get("start_time")
    end_str = params.get("end_time")
    bucket = params.get("bucket")
    key = params.get("key")

    if not start_str or not end_str or not bucket or not key:
        return {"error": "Missing one of start_time, end_time, bucket, or key"}

    try:
        # Convert input strings to datetime objects and ensure they are in UTC+7
        start_time = datetime.fromisoformat(start_str.replace("Z", "+07:00"))
        end_time = datetime.fromisoformat(end_str.replace("Z", "+07:00"))

        response = cloudtrail.lookup_events(
            StartTime=start_time,
            EndTime=end_time,
            MaxResults=50
        )
        cloudtrail_resources = []
        for event in response["Events"]:
            if "Create" in event["EventName"] or event["EventName"] in ["RunInstances", "CreateBucket"]:
                cloudtrail_resources.append({
                    "resource": event["Resources"],
                    "eventName": event["EventName"],
                    "userName": event.get("Username"),
                    "time": event["EventTime"].isoformat()
                })

        state_obj = s3.get_object(Bucket=bucket, Key=key)
        tfstate = json.load(state_obj["Body"])

        state_ids = set()
        for r in tfstate.get("resources", []):
            for i in r.get("instances", []):
                attrs = i.get("attributes", {})
                if "id" in attrs:
                    state_ids.add(attrs["id"])

        unmanaged = []
        for r in cloudtrail_resources:
            for res in r["resource"]:
                rid = res.get("ResourceName")
                if rid and rid not in state_ids:
                    unmanaged.append({
                        "resource_id": rid,
                        "event": r["eventName"],
                        "time": r["time"],
                        "user": r["userName"]
                    })

        return {"unmanaged_resources": unmanaged}

    except Exception as e:
        return {"error": str(e)}
