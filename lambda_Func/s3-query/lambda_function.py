import json
import boto3
from datetime import datetime
from typing import List, Optional

s3 = boto3.client('s3')
BUCKET_NAME = "statetf-bucket"
PREFIX = "drift-logs/"

def parse_iso_datetime(dt_str: str) -> datetime:
    # Handles date or datetime ISO-like strings
    # Example valid inputs: "2025-07-14" or "2025-07-14T10:25:19.220721"
    try:
        # Try parsing full datetime with microseconds
        return datetime.strptime(dt_str, "%Y-%m-%dT%H:%M:%S.%f")
    except ValueError:
        try:
            # Try parsing without fractional seconds
            return datetime.strptime(dt_str, "%Y-%m-%dT%H:%M:%S")
        except ValueError:
            # Try parsing just date
            return datetime.strptime(dt_str, "%Y-%m-%d")

def lambda_handler(event, context):
    """
    Expected event parameters are optional:
    - start_datetime: string, e.g. "2025-07-14" or "2025-07-14T10:00:00"
    - end_datetime: string, e.g. "2025-07-15" or "2025-07-14T12:00:00"
    
    If no dates provided, returns all logs.
    """
    
    start_str = event.get("start_datetime")
    end_str = event.get("end_datetime")

    start_dt: Optional[datetime] = parse_iso_datetime(start_str) if start_str else None
    end_dt: Optional[datetime] = parse_iso_datetime(end_str) if end_str else None

    # For date-only inputs, we want the entire day, so adjust range:
    # if time not present, start = 00:00:00 and end = 23:59:59.999999 for that day
    def adjust_range(dt: datetime, is_start: bool) -> datetime:
        if len(dt_str := dt.isoformat()) == 10: # Only date part
            if is_start:
                return datetime(dt.year, dt.month, dt.day, 0, 0, 0, 0)
            else:
                return datetime(dt.year, dt.month, dt.day, 23, 59, 59, 999999)
        return dt

    if start_dt:
        start_dt = adjust_range(start_dt, is_start=True)
    if end_dt:
        end_dt = adjust_range(end_dt, is_start=False)

    # List all files under prefix
    logs = []
    paginator = s3.get_paginator('list_objects_v2')
    page_iterator = paginator.paginate(Bucket=BUCKET_NAME, Prefix=PREFIX)

    for page in page_iterator:
        contents = page.get("Contents", [])
        for obj in contents:
            key = obj["Key"]
            if not key.endswith(".json"):
                continue
            # Extract filename without path
            filename = key.split("/")[-1]
            # Filename expected format: 2025-07-14T10:25:19.220721.json
            timestamp_str = filename[:-5]  # Remove ".json"

            try:
                file_dt = datetime.strptime(timestamp_str, "%Y-%m-%dT%H:%M:%S.%f")
            except ValueError:
                try:
                    file_dt = datetime.strptime(timestamp_str, "%Y-%m-%dT%H:%M:%S")
                except ValueError:
                    # Skip invalid filename format
                    continue

            # Check if file_dt in range
            if start_dt and file_dt < start_dt:
                continue
            if end_dt and file_dt > end_dt:
                continue

            # Fetch file contents from S3
            response = s3.get_object(Bucket=BUCKET_NAME, Key=key)
            content = response['Body'].read().decode('utf-8')
            # Parse JSON string content and store with its timestamp
            log_json = json.loads(content)
            logs.append( (file_dt.isoformat(), log_json) )

    # Sort logs by datetime
    logs.sort(key=lambda x: x[0])

    # Prepare output: formatted string for each log timestamp followed by its content pretty printed
    output = []
    for log_ts, log_content in logs:
        formatted_log = f"Log timestamp: {log_ts}\n{json.dumps(log_content, indent=2)}\n"
        output.append(formatted_log)

    return {
        "statusCode": 200,
        "logs": output,
        "count": len(output)
    }
