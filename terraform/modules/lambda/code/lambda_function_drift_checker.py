import json
import boto3
import os
from datetime import datetime, timedelta

def lambda_handler(event, context):
    s3 = boto3.client("s3")
    ec2 = boto3.client("ec2")
    sns = boto3.client("sns")
    cloudtrail = boto3.client("cloudtrail")
    
    bucket = os.environ.get("TFSTATE_BUCKET")
    key = os.environ.get("TFSTATE_KEY", "terraform.tfstate")
    sns_topic = os.environ.get("SNS_TOPIC_ARN")
    
    try:
        # Load Terraform state
        state_obj = s3.get_object(Bucket=bucket, Key=key)
        tfstate = json.loads(state_obj["Body"].read())
        
        # Extract managed resources with full attributes
        managed_resources = {}
        for resource in tfstate.get("resources", []):
            if resource["type"] == "aws_instance":
                for instance in resource.get("instances", []):
                    attrs = instance["attributes"]
                    managed_resources[attrs["id"]] = {
                        "type": "EC2",
                        "expected": {
                            "instance_type": attrs.get("instance_type"),
                            "tags": attrs.get("tags", {}),
                            "security_groups": attrs.get("security_groups", []),
                            "subnet_id": attrs.get("subnet_id")
                        }
                    }
            elif resource["type"] == "aws_s3_bucket":
                for instance in resource.get("instances", []):
                    attrs = instance["attributes"]
                    managed_resources[attrs["id"]] = {
                        "type": "S3",
                        "expected": {
                            "tags": attrs.get("tags", {})
                        }
                    }
            elif resource["type"] == "aws_iam_user":
                for instance in resource.get("instances", []):
                    attrs = instance["attributes"]
                    managed_resources[attrs["name"]] = {
                        "type": "IAM",
                        "expected": {
                            "arn": attrs.get("arn")
                        }
                    }
        
        # Get actual resources with full details
        actual_resources = discover_aws_resources()
        
        # Comprehensive drift analysis
        terraform_managed_drift = []
        unmanaged_resources_drift = []
        deleted_managed_resources = []
        
        # 1. Check configuration drift in Terraform-managed resources
        for resource_id in managed_resources:
            if resource_id in actual_resources:
                expected = managed_resources[resource_id].get("expected", {})
                actual = actual_resources[resource_id]  # Remove .get("actual") since structure changed
                resource_type = managed_resources[resource_id]["type"]
                
                changes = []
                for key in expected:
                    if expected[key] != actual.get(key):
                        changes.append(f"{key}: {expected[key]} -> {actual.get(key)}")
                
                if changes:
                    user_info = get_change_author(resource_id, cloudtrail)
                    terraform_managed_drift.append({
                        "resource_id": resource_id,
                        "type": resource_type,
                        "changes": changes,
                        "changed_by": user_info
                    })
        
        # 2. Check unmanaged resources (not managed by Terraform)
        unmanaged = set(actual_resources.keys()) - set(managed_resources.keys())
        print(f"Found {len(unmanaged)} unmanaged resources")
        
        # Process unmanaged resources with CloudTrail lookup for IAM only
        for resource_id in list(unmanaged)[:5]:  # Limit to 5 to avoid timeout
            resource_info = actual_resources[resource_id]
            resource_type = resource_info["type"]
            service = resource_info["service"]
            
            # Only do CloudTrail lookup for IAM resources (they're in us-east-1)
            if service == "iam":
                user_info = get_change_author(resource_id, cloudtrail)
            else:
                user_info = {"user": "unknown", "event": "unknown", "time": "unknown", "region": "unknown"}
            
            unmanaged_resources_drift.append({
                "resource_id": resource_id,
                "type": resource_type,
                "service": service,
                "created_by": user_info
            })
        
        # 3. Check deleted managed resources
        deleted = set(managed_resources.keys()) - set(actual_resources.keys())
        for resource_id in deleted:
            resource_type = managed_resources[resource_id]["type"]
            user_info = get_change_author(resource_id, cloudtrail)
            deleted_managed_resources.append({
                "resource_id": resource_id,
                "type": resource_type,
                "deleted_by": user_info
            })
        
        drift_found = terraform_managed_drift or unmanaged_resources_drift or deleted_managed_resources
        
        if drift_found:
            summary = generate_detailed_summary(terraform_managed_drift, unmanaged_resources_drift, deleted_managed_resources)
            sns.publish(TopicArn=sns_topic, Subject="Infrastructure Drift Detected", Message=summary)
            return {
                "drift_detected": True, 
                "summary": summary,
                "terraform_managed_drift": terraform_managed_drift,
                "unmanaged_resources": unmanaged_resources_drift,
                "deleted_managed_resources": deleted_managed_resources
            }
        
        return {"drift_detected": False, "summary": "No drift detected"}
        
    except Exception as e:
        error_msg = f"Error: {str(e)}"
        print(error_msg)
        return {"error": error_msg}

def discover_aws_resources():
    """Discover AWS resources with parallel processing"""
    resources = {}
    
    # Priority services (most common)
    priority_services = [
        ("EC2", lambda: discover_ec2()),
        ("S3", lambda: discover_s3()),
        ("Lambda", lambda: discover_lambda()),
        ("IAM", lambda: discover_iam())
    ]
    
    # Discover priority services first
    for service_name, discover_func in priority_services:
        try:
            print(f"Discovering {service_name} resources...")
            service_resources = discover_func()
            resources.update(service_resources)
        except Exception as e:
            print(f"Failed to discover {service_name}: {e}")
    
    return resources

def discover_ec2():
    resources = {}
    ec2 = boto3.client("ec2")
    
    # EC2 instances
    for reservation in ec2.describe_instances()["Reservations"]:
        for instance in reservation["Instances"]:
            if instance["State"]["Name"] != "terminated":
                resources[instance["InstanceId"]] = {"type": "EC2", "service": "ec2"}
    
    # VPCs
    for vpc in ec2.describe_vpcs()["Vpcs"]:
        resources[vpc["VpcId"]] = {"type": "VPC", "service": "ec2"}
    
    return resources

def discover_s3():
    resources = {}
    s3 = boto3.client("s3")
    
    for bucket in s3.list_buckets()["Buckets"]:
        resources[bucket["Name"]] = {"type": "S3", "service": "s3"}
    
    return resources

def discover_lambda():
    resources = {}
    lambda_client = boto3.client("lambda")
    
    for func in lambda_client.list_functions()["Functions"]:
        resources[func["FunctionName"]] = {"type": "Lambda", "service": "lambda"}
    
    return resources

def discover_iam():
    resources = {}
    iam = boto3.client("iam")
    
    try:
        print("Listing IAM users...")
        response = iam.list_users()
        users = response.get("Users", [])
        print(f"Found {len(users)} IAM users")
        
        for user in users:
            username = user.get("UserName", "noname")
            print(f"IAM user found: {username}")
            if username and username != "noname":
                resources[username] = {"type": "IAM", "service": "iam"}
    except Exception as e:
        print(f"Error listing IAM users: {e}")
    
    return resources

def get_change_author(resource_id, cloudtrail):
    # Regions to check for CloudTrail events
    regions_to_check = ['ap-southeast-1', 'us-east-1']  # Current region + us-east-1 for global services
    
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(days=7)  # Extend search to 7 days
    
    print(f"Searching for events for resource: {resource_id}")
    
    for region in regions_to_check:
        try:
            print(f"Checking region: {region}")
            # Create CloudTrail client for specific region
            regional_cloudtrail = boto3.client('cloudtrail', region_name=region)
            
            # Try multiple search methods based on resource type
            search_methods = []
            
            # For IAM resources, search by EventName first (more efficient)
            if not resource_id.startswith('i-') and not resource_id.startswith('vpc-'):
                search_methods.append({"AttributeKey": "EventName", "AttributeValue": "CreateUser"})
            
            # Always try ResourceName as fallback
            search_methods.append({"AttributeKey": "ResourceName", "AttributeValue": resource_id})
            
            for search_attr in search_methods:
                if search_attr is None:
                    continue
                    
                print(f"Searching with: {search_attr}")
                events = regional_cloudtrail.lookup_events(
                    LookupAttributes=[search_attr],
                    StartTime=start_time,
                    EndTime=end_time,
                    MaxResults=10
                )
                
                # Filter events for our specific resource
                for event in events.get("Events", []):
                    event_detail = json.loads(event["CloudTrailEvent"])
                    
                    # Check if this event is related to our resource
                    if (resource_id in str(event_detail) or 
                        any(resource_id in str(resource.get("resourceName", "")) for resource in event.get("Resources", []))):
                        
                        user_identity = event_detail.get("userIdentity", {})
                        result = {
                            "user": user_identity.get("arn", "unknown").split("/")[-1] if user_identity.get("arn") else "unknown",
                            "event": event["EventName"],
                            "time": event["EventTime"].strftime("%Y-%m-%d %H:%M:%S"),
                            "region": region
                        }
                        print(f"Found event: {result}")
                        return result
                        
        except Exception as e:
            print(f"CloudTrail lookup failed for {resource_id} in {region}: {e}")
            continue
    
    print(f"No events found for {resource_id} in any region")
    return {"user": "unknown", "event": "unknown", "time": "unknown", "region": "unknown"}

def generate_detailed_summary(terraform_drift, unmanaged_resources, deleted_resources):
    summary = "=== INFRASTRUCTURE DRIFT REPORT ===\n\n"
    
    if terraform_drift:
        summary += f"🔧 TERRAFORM-MANAGED RESOURCES WITH DRIFT ({len(terraform_drift)}):\n"
        for resource in terraform_drift:
            user_info = resource['changed_by']
            summary += f"   • {resource['type']} {resource['resource_id']}\n"
            summary += f"     Modified by: {user_info['user']} at {user_info['time']}\n"
            if 'region' in user_info:
                summary += f"     CloudTrail region: {user_info['region']}\n"
            summary += f"     Event: {user_info['event']}\n"
            for change in resource['changes']:
                summary += f"     - {change}\n"
        summary += "\n"
    
    if unmanaged_resources:
        summary += f"⚠️  UNMANAGED RESOURCES (NOT IN TERRAFORM) ({len(unmanaged_resources)}):\n"
        for resource in unmanaged_resources:
            user_info = resource['created_by']
            service = resource.get('service', 'unknown')
            summary += f"   • {resource['type']} {resource['resource_id']} ({service})\n"
            summary += f"     Created by: {user_info['user']} at {user_info['time']}\n"
            if 'region' in user_info:
                summary += f"     CloudTrail region: {user_info['region']}\n"
            summary += f"     Event: {user_info['event']}\n"
        summary += "\n"
    
    if deleted_resources:
        summary += f"❌ DELETED TERRAFORM-MANAGED RESOURCES ({len(deleted_resources)}):\n"
        for resource in deleted_resources:
            user_info = resource['deleted_by']
            summary += f"   • {resource['type']} {resource['resource_id']}\n"
            summary += f"     Deleted by: {user_info['user']} at {user_info['time']}\n"
            if 'region' in user_info:
                summary += f"     CloudTrail region: {user_info['region']}\n"
            summary += f"     Event: {user_info['event']}\n"
    
    return summary

