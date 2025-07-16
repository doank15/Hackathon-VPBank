import json
import boto3
import os

def lambda_handler(event, context):
    """Real-time drift detection triggered by AWS Config changes"""
    s3 = boto3.client("s3")
    sns = boto3.client("sns")
    cloudtrail = boto3.client("cloudtrail")
    
    bucket = os.environ.get("TFSTATE_BUCKET")
    key = os.environ.get("TFSTATE_KEY", "terraform.tfstate")
    sns_topic = os.environ.get("SNS_TOPIC_ARN")
    
    # Parse Config event
    config_item = event.get("configurationItem")
    if not config_item:
        return {"message": "No configuration item found"}
    
    resource_id = config_item["resourceId"]
    resource_type = config_item["resourceType"]
    config_status = config_item["configurationItemStatus"]
    
    # Skip if resource is being deleted
    if config_status == "ResourceDeleted":
        return {"message": "Resource deletion - skipping"}
    
    try:
        # Load Terraform state
        state_obj = s3.get_object(Bucket=bucket, Key=key)
        tfstate = json.loads(state_obj["Body"].read())
        
        # Check if resource is managed by Terraform
        is_managed = is_terraform_managed(resource_id, tfstate)
        
        if is_managed:
            # Get expected vs actual configuration
            drift_details = check_config_drift(resource_id, resource_type, config_item, tfstate)
            if drift_details:
                # Get who made the change
                user_info = get_change_author(resource_id, cloudtrail)
                
                message = f"""🔧 TERRAFORM-MANAGED RESOURCE DRIFT DETECTED

Resource: {resource_type} {resource_id}
Modified by: {user_info['user']} at {user_info['time']}
Event: {user_info['event']}
Region: {user_info.get('region', 'unknown')}

Configuration Changes:
{drift_details}"""
                
                sns.publish(TopicArn=sns_topic, Subject="Real-time Drift Detected", Message=message)
                return {"drift_detected": True, "message": message}
        else:
            # Unmanaged resource detected
            user_info = get_change_author(resource_id, cloudtrail)
            
            message = f"""⚠️ UNMANAGED RESOURCE DETECTED

Resource: {resource_type} {resource_id}
Created by: {user_info['user']} at {user_info['time']}
Event: {user_info['event']}
Region: {user_info.get('region', 'unknown')}

This resource is not managed by Terraform."""
            
            sns.publish(TopicArn=sns_topic, Subject="Unmanaged Resource Detected", Message=message)
            return {"unmanaged_resource": True, "message": message}
            
    except Exception as e:
        error_msg = f"Error processing config change: {str(e)}"
        print(error_msg)
        return {"error": error_msg}
    
    return {"message": "No drift detected"}

def is_terraform_managed(resource_id, tfstate):
    """Check if resource is managed by Terraform"""
    for resource in tfstate.get("resources", []):
        for instance in resource.get("instances", []):
            if instance["attributes"].get("id") == resource_id:
                return True
    return False

def check_config_drift(resource_id, resource_type, config_item, tfstate):
    """Compare actual config with Terraform state"""
    # Find expected configuration in Terraform state
    expected_config = None
    for resource in tfstate.get("resources", []):
        for instance in resource.get("instances", []):
            if instance["attributes"].get("id") == resource_id:
                expected_config = instance["attributes"]
                break
    
    if not expected_config:
        return None
    
    # Compare configurations based on resource type
    drift_details = []
    actual_config = config_item.get("configuration", {})
    
    if resource_type == "AWS::EC2::Instance":
        # Check instance type
        expected_type = expected_config.get("instance_type")
        actual_type = actual_config.get("instanceType")
        if expected_type != actual_type:
            drift_details.append(f"- Instance Type: {expected_type} -> {actual_type}")
        
        # Check tags
        expected_tags = expected_config.get("tags", {})
        actual_tags = {tag["key"]: tag["value"] for tag in actual_config.get("tags", [])}
        if expected_tags != actual_tags:
            drift_details.append(f"- Tags: {expected_tags} -> {actual_tags}")
    
    elif resource_type == "AWS::S3::Bucket":
        # Check bucket tags
        expected_tags = expected_config.get("tags", {})
        actual_tags = {tag["key"]: tag["value"] for tag in actual_config.get("tags", [])}
        if expected_tags != actual_tags:
            drift_details.append(f"- Tags: {expected_tags} -> {actual_tags}")
    
    return "\n".join(drift_details) if drift_details else None

def get_change_author(resource_id, cloudtrail):
    """Get who made the change from CloudTrail - check multiple regions"""
    from datetime import datetime, timedelta
    import boto3
    
    regions_to_check = ['ap-southeast-1', 'us-east-1']  # Current + global services region
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(minutes=30)
    
    for region in regions_to_check:
        try:
            regional_cloudtrail = boto3.client('cloudtrail', region_name=region)
            
            events = regional_cloudtrail.lookup_events(
                LookupAttributes=[{
                    "AttributeKey": "ResourceName",
                    "AttributeValue": resource_id
                }],
                StartTime=start_time,
                EndTime=end_time,
                MaxResults=1
            )
            
            if events.get("Events"):
                latest_event = events["Events"][0]
                event_detail = json.loads(latest_event["CloudTrailEvent"])
                user_identity = event_detail.get("userIdentity", {})
                return {
                    "user": user_identity.get("arn", "unknown").split("/")[-1] if user_identity.get("arn") else "unknown",
                    "event": latest_event["EventName"],
                    "time": latest_event["EventTime"].strftime("%Y-%m-%d %H:%M:%S"),
                    "region": region
                }
        except Exception as e:
            print(f"CloudTrail lookup failed in {region}: {e}")
            continue
    
    return {"user": "unknown", "event": "unknown", "time": "unknown", "region": "unknown"}