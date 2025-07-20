import json
import boto3
import os
from datetime import datetime, timedelta

def lambda_handler(event, context):
    """Main handler for drift detection"""
    print(f"Received event: {json.dumps(event)}")
    
    # Check if this is a Config event from EventBridge
    if event.get("detail-type") == "Config Configuration Item Change" and event.get("detail") and event["detail"].get("configurationItem"):
        print("Processing AWS Config change event from EventBridge")
        return handle_config_change(event)
    
    # Check if this is a CloudTrail API call event from EventBridge
    if event.get("detail-type") == "AWS API Call via CloudTrail" and event.get("detail"):
        print("Processing CloudTrail API call event from EventBridge")
        return handle_cloudtrail_event(event)
    
    # Check if this is a Config event (direct invocation)
    if event.get("detail") and event["detail"].get("configurationItem"):
        print("Processing AWS Config change event (direct)")
        return handle_config_change(event)
    
    # Check if this is an S3 event (state file change) from EventBridge
    if event.get("detail-type") == "Object Created" and event.get("detail") and event["detail"].get("object") and event["detail"]["object"].get("key", "").endswith(".tfstate"):
        print("Processing S3 state file change event from EventBridge")
        return handle_state_change_eventbridge(event)
    
    # Check if this is an S3 event (state file change) from S3 notification
    if event.get("Records") and event["Records"][0].get("s3"):
        print("Processing S3 state file change event from S3 notification")
        return handle_state_change(event)
    
    # Check if this is a test event with state comparison
    if event.get("test") == "state_comparison" and event.get("prev_state") and event.get("current_state"):
        print("Processing test state comparison")
        changes = compare_terraform_states(event["prev_state"], event["current_state"])
        if changes:
            summary = generate_state_change_summary(changes)
            return {
                "state_changed": True,
                "changes": changes,
                "summary": summary
            }
        return {"state_changed": False}
    
    # If it's a scheduled event or manual invocation, run full drift detection
    print("Running full drift detection")
    return run_full_drift_detection()
    
    # If it's a scheduled event or manual invocation, run full drift detection
    print("Running full drift detection")
    return run_full_drift_detection()

def run_full_drift_detection():
    """Run comprehensive drift detection"""
    s3 = boto3.client("s3")
    sns = boto3.client("sns")
    lambda_client = boto3.client("lambda")
    
    bucket = os.environ.get("TFSTATE_BUCKET")
    key = os.environ.get("TFSTATE_KEY", "terraform.tfstate")
    sns_topic = os.environ.get("SNS_TOPIC_ARN")
    bedrock_analyzer_arn = os.environ.get("BEDROCK_ANALYZER_ARN")
    
    try:
        # Load Terraform state
        state_obj = s3.get_object(Bucket=bucket, Key=key)
        tfstate = json.loads(state_obj["Body"].read())
        
        # Extract managed resources
        managed_resources = extract_managed_resources(tfstate)
        
        # Get actual resources
        actual_resources = get_actual_resources()
        
        # Find drift
        unmanaged_resources = []
        deleted_resources = []
        modified_resources = []
        
        # 1. Unmanaged resources (not in Terraform)
        for resource_id, details in actual_resources.items():
            if resource_id not in managed_resources:
                # Get who created this resource
                creator_info = get_change_author(resource_id, details["type"])
                unmanaged_resources.append({
                    "id": resource_id,
                    "type": details["type"],
                    "created_by": creator_info
                })
        
        # 2. Deleted resources (in Terraform but not in AWS)
        for resource_id, details in managed_resources.items():
            if resource_id not in actual_resources:
                # Get who deleted this resource
                deleter_info = get_change_author(resource_id, details["type"])
                deleted_resources.append({
                    "id": resource_id,
                    "type": details["type"],
                    "deleted_by": deleter_info
                })
        
        # 3. Modified resources (attributes differ between Terraform and actual)
        for resource_id, tf_details in managed_resources.items():
            if resource_id in actual_resources:
                actual_details = actual_resources[resource_id]
                
                # Compare attributes
                changes = []
                
                # For EC2 instances
                if tf_details["type"] == "aws_instance" and actual_details["type"] == "EC2":
                    tf_attrs = tf_details["attributes"]
                    actual_attrs = actual_details["attributes"]
                    
                    # Check instance type
                    if tf_attrs.get("instance_type") != actual_attrs.get("instance_type"):
                        changes.append({
                            "attribute": "instance_type",
                            "expected": tf_attrs.get("instance_type"),
                            "actual": actual_attrs.get("instance_type")
                        })
                    
                    # Check tags
                    if tf_attrs.get("tags") != actual_attrs.get("tags"):
                        changes.append({
                            "attribute": "tags",
                            "expected": tf_attrs.get("tags"),
                            "actual": actual_attrs.get("tags")
                        })
                
                # For S3 buckets
                elif tf_details["type"] == "aws_s3_bucket" and actual_details["type"] == "S3":
                    tf_attrs = tf_details["attributes"]
                    actual_attrs = actual_details["attributes"]
                    
                    # Check tags
                    if tf_attrs.get("tags") != actual_attrs.get("tags"):
                        changes.append({
                            "attribute": "tags",
                            "expected": tf_attrs.get("tags"),
                            "actual": actual_attrs.get("tags")
                        })
                
                # For RDS instances
                elif tf_details["type"] == "aws_db_instance" and actual_details["type"] == "RDS":
                    tf_attrs = tf_details["attributes"]
                    actual_attrs = actual_details["attributes"]
                    
                    # Check instance class
                    if tf_attrs.get("instance_class") != actual_attrs.get("instance_class"):
                        changes.append({
                            "attribute": "instance_class",
                            "expected": tf_attrs.get("instance_class"),
                            "actual": actual_attrs.get("instance_class")
                        })
                    
                    # Check storage size
                    if tf_attrs.get("allocated_storage") != actual_attrs.get("storage_size"):
                        changes.append({
                            "attribute": "allocated_storage",
                            "expected": tf_attrs.get("allocated_storage"),
                            "actual": actual_attrs.get("storage_size")
                        })
                    
                    # Check Multi-AZ
                    if tf_attrs.get("multi_az") != actual_attrs.get("multi_az"):
                        changes.append({
                            "attribute": "multi_az",
                            "expected": tf_attrs.get("multi_az"),
                            "actual": actual_attrs.get("multi_az")
                        })
                    
                    # Check tags
                    if tf_attrs.get("tags") != actual_attrs.get("tags"):
                        changes.append({
                            "attribute": "tags",
                            "expected": tf_attrs.get("tags"),
                            "actual": actual_attrs.get("tags")
                        })
                
                if changes:
                    # Get who made the change
                    modifier_info = get_change_author(resource_id, actual_details["type"])
                    
                    modified_resources.append({
                        "id": resource_id,
                        "type": tf_details["type"],
                        "changes": changes,
                        "modified_by": modifier_info
                    })
        
        # Generate report
        drift_found = unmanaged_resources or deleted_resources or modified_resources
        if drift_found:
            # Generate technical summary for logging
            summary = generate_summary(unmanaged_resources, deleted_resources, modified_resources)
            
            # Call Bedrock analyzer for human-readable analysis
            if bedrock_analyzer_arn:
                try:
                    # Prepare detailed drift report for Bedrock
                    drift_report = {
                        "unmanaged_resources": unmanaged_resources,
                        "deleted_resources": deleted_resources,
                        "modified_resources": modified_resources,
                        "summary": summary,
                        "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
                    }
                    
                    print(f"Invoking Bedrock analyzer: {bedrock_analyzer_arn}")
                    # Invoke Bedrock analyzer asynchronously
                    response = lambda_client.invoke(
                        FunctionName=bedrock_analyzer_arn,
                        InvocationType='Event',  # Asynchronous
                        Payload=json.dumps({
                            "drift_report": drift_report
                        })
                    )
                    print(f"Bedrock analyzer invoked: {response}")
                except Exception as e:
                    print(f"Error invoking Bedrock analyzer: {e}")
                    # Fallback to direct SNS notification if Bedrock fails
                    sns.publish(TopicArn=sns_topic, Subject="Infrastructure Drift Detected (Bedrock Failed)", Message=summary)
            else:
                # Fallback if Bedrock analyzer ARN is not configured
                sns.publish(TopicArn=sns_topic, Subject="Infrastructure Drift Detected", Message=summary)
            
            return {
                "drift_detected": True,
                "unmanaged_count": len(unmanaged_resources),
                "deleted_count": len(deleted_resources),
                "modified_count": len(modified_resources),
                "summary": summary
            }
        
        return {"drift_detected": False}
        
    except Exception as e:
        return {"error": str(e)}

def extract_managed_resources(tfstate):
    """Extract resources managed by Terraform"""
    managed_resources = {}
    
    for resource in tfstate.get("resources", []):
        for instance in resource.get("instances", []):
            attrs = instance.get("attributes", {})
            resource_id = attrs.get("id") or attrs.get("name")
            if resource_id:
                managed_resources[resource_id] = {
                    "type": resource["type"],
                    "attributes": attrs
                }
    
    return managed_resources

def get_actual_resources():
    """Get actual AWS resources with detailed attributes for drift detection"""
    actual_resources = {}
    
    # EC2 instances
    try:
        ec2 = boto3.client("ec2")
        for reservation in ec2.describe_instances()["Reservations"]:
            for instance in reservation["Instances"]:
                if instance["State"]["Name"] != "terminated":
                    actual_resources[instance["InstanceId"]] = {
                        "type": "EC2",
                        "attributes": {
                            "instance_type": instance.get("InstanceType"),
                            "tags": {tag["Key"]: tag["Value"] for tag in instance.get("Tags", [])},
                            "subnet_id": instance.get("SubnetId"),
                            "security_groups": [sg["GroupId"] for sg in instance.get("SecurityGroups", [])]
                        }
                    }
    except Exception as e:
        print(f"Error getting EC2 instances: {e}")
    
    # S3 buckets
    try:
        s3 = boto3.client("s3")
        for bucket in s3.list_buckets()["Buckets"]:
            try:
                tags_response = s3.get_bucket_tagging(Bucket=bucket["Name"])
                tags = {tag["Key"]: tag["Value"] for tag in tags_response.get("TagSet", [])}
            except:
                tags = {}
                
            actual_resources[bucket["Name"]] = {
                "type": "S3",
                "attributes": {
                    "tags": tags
                }
            }
    except Exception as e:
        print(f"Error getting S3 buckets: {e}")
    
    # IAM users
    try:
        iam = boto3.client("iam")
        for user in iam.list_users()["Users"]:
            actual_resources[user["UserName"]] = {
                "type": "IAM",
                "attributes": {
                    "arn": user.get("Arn"),
                    "path": user.get("Path")
                }
            }
    except Exception as e:
        print(f"Error getting IAM users: {e}")
    
    # RDS instances
    try:
        rds = boto3.client("rds")
        for db in rds.describe_db_instances()["DBInstances"]:
            # Get tags
            try:
                tags = {tag["Key"]: tag["Value"] for tag in rds.list_tags_for_resource(
                    ResourceName=db["DBInstanceArn"]
                ).get("TagList", [])}
            except:
                tags = {}
                
            actual_resources[db["DBInstanceIdentifier"]] = {
                "type": "RDS",
                "attributes": {
                    "engine": db.get("Engine"),
                    "instance_class": db.get("DBInstanceClass"),
                    "storage_size": db.get("AllocatedStorage"),
                    "multi_az": db.get("MultiAZ"),
                    "tags": tags
                }
            }
    except Exception as e:
        print(f"Error getting RDS instances: {e}")
    
    return actual_resources

def get_change_author(resource_id, resource_type):
    """Get who made changes to a resource"""
    # Determine which region to check based on resource type
    regions = ["ap-southeast-1"]
    if resource_type == "IAM":
        regions = ["us-east-1"]
    
    # For deleted resources, we need to check a longer time period
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(days=30)  # Extend to 30 days
    
    # First try resource-specific lookup
    for region in regions:
        try:
            ct = boto3.client("cloudtrail", region_name=region)
            
            # Determine relevant event names based on resource type
            event_names = []
            if resource_type == "EC2" or resource_type == "aws_instance":
                event_names = ["ModifyInstanceAttribute", "CreateTags", "RunInstances", "TerminateInstances"]
            elif resource_type == "S3" or resource_type == "aws_s3_bucket":
                event_names = ["PutBucketTagging", "PutBucketPolicy", "CreateBucket", "DeleteBucket"]
            elif resource_type == "IAM" or resource_type == "aws_iam_user":
                event_names = ["UpdateUser", "AttachUserPolicy", "CreateUser", "DeleteUser"]
            elif resource_type == "RDS" or resource_type == "aws_db_instance":
                event_names = ["ModifyDBInstance", "AddTagsToResource", "CreateDBInstance", "DeleteDBInstance"]
            elif resource_type == "aws_vpc" or "vpc" in resource_type.lower():
                event_names = ["CreateVpc", "DeleteVpc", "ModifyVpcAttribute"]
            elif resource_type == "aws_subnet" or "subnet" in resource_type.lower():
                event_names = ["CreateSubnet", "DeleteSubnet", "ModifySubnetAttribute"]
            
            # Search for events by resource name
            try:
                events = ct.lookup_events(
                    LookupAttributes=[
                        {"AttributeKey": "ResourceName", "AttributeValue": resource_id}
                    ],
                    StartTime=start_time,
                    EndTime=end_time,
                    MaxResults=10
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
                print(f"Error looking up events by resource name for {resource_id}: {e}")
            
            # If resource name lookup failed, try event name lookup
            for event_name in event_names:
                try:
                    events = ct.lookup_events(
                        LookupAttributes=[
                            {"AttributeKey": "EventName", "AttributeValue": event_name}
                        ],
                        StartTime=start_time,
                        EndTime=end_time,
                        MaxResults=100
                    )
                    
                    # Search through events for our resource ID
                    for event in events.get("Events", []):
                        event_detail = json.loads(event["CloudTrailEvent"])
                        if resource_id in str(event_detail):
                            user_identity = event_detail.get("userIdentity", {})
                            return {
                                "user": user_identity.get("arn", "unknown").split("/")[-1] if user_identity.get("arn") else "unknown",
                                "event": event["EventName"],
                                "time": event["EventTime"].strftime("%Y-%m-%d %H:%M:%S"),
                                "region": region
                            }
                except Exception as e:
                    print(f"Error looking up event {event_name} for {resource_id}: {e}")
                    continue
        except Exception as e:
            print(f"Error checking CloudTrail in {region}: {e}")
    
    # For deleted resources, check for terraform apply events
    try:
        ct = boto3.client("cloudtrail", region_name=regions[0])
        events = ct.lookup_events(
            LookupAttributes=[
                {"AttributeKey": "EventName", "AttributeValue": "ApplyProviderChanges"}
            ],
            StartTime=start_time,
            EndTime=end_time,
            MaxResults=20
        )
        
        for event in events.get("Events", []):
            event_detail = json.loads(event["CloudTrailEvent"])
            if "terraform" in str(event_detail).lower():
                user_identity = event_detail.get("userIdentity", {})
                return {
                    "user": user_identity.get("arn", "unknown").split("/")[-1] if user_identity.get("arn") else "unknown",
                    "event": "Terraform Apply",
                    "time": event["EventTime"].strftime("%Y-%m-%d %H:%M:%S"),
                    "region": regions[0]
                }
    except Exception as e:
        print(f"Error checking for Terraform events: {e}")
    
    # If no events found
    return {
        "user": "unknown",
        "event": "unknown",
        "time": "unknown",
        "region": "unknown"
    }

def handle_config_change(event):
    """Handle AWS Config change events"""
    sns = boto3.client("sns")
    sns_topic = os.environ.get("SNS_TOPIC_ARN")
    
    try:
        # Extract config item
        config_item = event["detail"]["configurationItem"]
        resource_id = config_item["resourceId"]
        resource_type = config_item["resourceType"]
        change_type = config_item["configurationItemStatus"]
        
        # Check if this is a Terraform-managed resource
        is_managed = is_terraform_managed(resource_id)
        
        # Get who made the change
        user_info = get_change_author(resource_id, resource_type.split("::")[-1])
        
        # Generate summary
        summary = f"CONFIG CHANGE DETECTED\n\n"
        summary += f"Resource: {resource_type} {resource_id}\n"
        summary += f"Change Type: {change_type}\n"
        summary += f"Changed By: {user_info['user']}\n"
        summary += f"Change Time: {user_info['time']}\n"
        summary += f"Region: {user_info['region']}\n"
        summary += f"Terraform Managed: {'Yes' if is_managed else 'No'}\n"
        
        # Add configuration differences if available
        if event["detail"].get("configurationItemDiff"):
            config_diff = event["detail"]["configurationItemDiff"]
            if config_diff.get("changedProperties"):
                summary += "\nChanged Properties:\n"
                for prop_name, prop_change in config_diff["changedProperties"].items():
                    if prop_change.get("previousValue") and prop_change.get("updatedValue"):
                        summary += f"  - {prop_name}: {prop_change['previousValue']} -> {prop_change['updatedValue']}\n"
        
        # Send notification
        sns.publish(TopicArn=sns_topic, Subject="Config Change Detected", Message=summary)
        
        return {
            "config_change": True,
            "resource_id": resource_id,
            "resource_type": resource_type,
            "terraform_managed": is_managed,
            "changed_by": user_info,
            "summary": summary
        }
    except Exception as e:
        print(f"Error handling Config change: {e}")
        return {"error": str(e)}

def handle_cloudtrail_event(event):
    """Handle CloudTrail API call events from EventBridge"""
    sns = boto3.client("sns")
    sns_topic = os.environ.get("SNS_TOPIC_ARN")
    
    try:
        # Extract event details
        detail = event["detail"]
        event_name = detail["eventName"]
        event_source = detail["eventSource"].split(".")[0]  # e.g., ec2.amazonaws.com -> ec2
        event_time = detail["eventTime"]
        
        # Get user identity
        user_identity = detail.get("userIdentity", {})
        user = user_identity.get("arn", "unknown").split("/")[-1] if user_identity.get("arn") else "unknown"
        
        # Extract resource information
        resources = []
        if detail.get("responseElements"):
            if event_name == "RunInstances" and detail["responseElements"].get("instancesSet"):
                instances = detail["responseElements"]["instancesSet"].get("items", [])
                for instance in instances:
                    resources.append({
                        "type": "EC2 Instance",
                        "id": instance.get("instanceId", "unknown")
                    })
            elif event_name == "CreateBucket" and detail["responseElements"].get("BucketName"):
                resources.append({
                    "type": "S3 Bucket",
                    "id": detail["responseElements"]["BucketName"]
                })
            elif event_name == "CreateDBInstance" and detail["responseElements"].get("dBInstanceIdentifier"):
                resources.append({
                    "type": "RDS Instance",
                    "id": detail["responseElements"]["dBInstanceIdentifier"]
                })
        
        # Generate summary
        summary = f"API CALL DETECTED\n\n"
        summary += f"Event: {event_name}\n"
        summary += f"Service: {event_source}\n"
        summary += f"Time: {event_time}\n"
        summary += f"User: {user}\n\n"
        
        if resources:
            summary += "Affected Resources:\n"
            for resource in resources:
                summary += f"  - {resource['type']}: {resource['id']}\n"
                # Check if this is a Terraform-managed resource
                is_managed = is_terraform_managed(resource['id'])
                summary += f"    Terraform Managed: {'Yes' if is_managed else 'No'}\n"
        
        # Send notification
        sns.publish(TopicArn=sns_topic, Subject=f"API Call Detected: {event_name}", Message=summary)
        
        return {
            "api_call": True,
            "event_name": event_name,
            "user": user,
            "resources": resources,
            "summary": summary
        }
    except Exception as e:
        print(f"Error handling CloudTrail event: {e}")
        return {"error": str(e)}

def handle_state_change_eventbridge(event):
    """Handle S3 state file changes from EventBridge"""
    s3 = boto3.client("s3")
    sns = boto3.client("sns")
    sns_topic = os.environ.get("SNS_TOPIC_ARN")
    
    try:
        # Get bucket and key from event
        bucket = event["detail"]["bucket"]["name"]
        key = event["detail"]["object"]["key"]
        
        # Get current state file
        current_state_obj = s3.get_object(Bucket=bucket, Key=key)
        current_state = json.loads(current_state_obj["Body"].read())
        
        # Get previous state file version if available
        try:
            versions = s3.list_object_versions(Bucket=bucket, Prefix=key)["Versions"]
            if len(versions) > 1:
                prev_version_id = versions[1]["VersionId"]
                prev_state_obj = s3.get_object(Bucket=bucket, Key=key, VersionId=prev_version_id)
                prev_state = json.loads(prev_state_obj["Body"].read())
            else:
                return {"message": "No previous state version found"}
        except Exception as e:
            print(f"Error getting previous state: {e}")
            return {"message": "No previous state available"}
        
        # Compare states to find changes
        changes = compare_terraform_states(prev_state, current_state)
        
        if changes:
            # Generate summary
            summary = generate_state_change_summary(changes)
            
            # Send notification
            sns.publish(TopicArn=sns_topic, Subject="Terraform State Change Detected", Message=summary)
            
            return {
                "state_changed": True,
                "changes": changes,
                "summary": summary
            }
        
        return {"state_changed": False}
        
    except Exception as e:
        print(f"Error handling state change from EventBridge: {e}")
        return {"error": str(e)}

def is_terraform_managed(resource_id):
    """Check if a resource is managed by Terraform"""
    try:
        s3 = boto3.client("s3")
        bucket = os.environ.get("TFSTATE_BUCKET")
        key = os.environ.get("TFSTATE_KEY", "terraform.tfstate")
        
        # Load Terraform state
        state_obj = s3.get_object(Bucket=bucket, Key=key)
        tfstate = json.loads(state_obj["Body"].read())
        
        # Check if resource is in state
        for resource in tfstate.get("resources", []):
            for instance in resource.get("instances", []):
                attrs = instance.get("attributes", {})
                tf_resource_id = attrs.get("id") or attrs.get("name")
                if tf_resource_id == resource_id:
                    return True
        
        return False
    except Exception as e:
        print(f"Error checking if resource is Terraform managed: {e}")
        return False

def handle_state_change(event):
    """Handle Terraform state file changes"""
    s3 = boto3.client("s3")
    sns = boto3.client("sns")
    sns_topic = os.environ.get("SNS_TOPIC_ARN")
    
    try:
        # Get bucket and key from event
        bucket = event["Records"][0]["s3"]["bucket"]["name"]
        key = event["Records"][0]["s3"]["object"]["key"]
        
        # Get current state file
        current_state_obj = s3.get_object(Bucket=bucket, Key=key)
        current_state = json.loads(current_state_obj["Body"].read())
        
        # Get previous state file version if available
        try:
            versions = s3.list_object_versions(Bucket=bucket, Prefix=key)["Versions"]
            if len(versions) > 1:
                prev_version_id = versions[1]["VersionId"]
                prev_state_obj = s3.get_object(Bucket=bucket, Key=key, VersionId=prev_version_id)
                prev_state = json.loads(prev_state_obj["Body"].read())
            else:
                return {"message": "No previous state version found"}
        except Exception as e:
            print(f"Error getting previous state: {e}")
            return {"message": "No previous state available"}
        
        # Compare states to find changes
        changes = compare_terraform_states(prev_state, current_state)
        
        if changes:
            # Generate summary
            summary = generate_state_change_summary(changes)
            
            # Send notification
            sns.publish(TopicArn=sns_topic, Subject="Terraform State Change Detected", Message=summary)
            
            return {
                "state_changed": True,
                "changes": changes,
                "summary": summary
            }
        
        return {"state_changed": False}
        
    except Exception as e:
        return {"error": str(e)}

def compare_terraform_states(prev_state, current_state):
    """Compare two Terraform states to find changes"""
    changes = []
    
    # Extract resources from both states
    prev_resources = {}
    current_resources = {}
    
    # Process previous state
    for resource in prev_state.get("resources", []):
        for instance in resource.get("instances", []):
            attrs = instance.get("attributes", {})
            resource_id = attrs.get("id") or attrs.get("name")
            if resource_id:
                prev_resources[resource_id] = {
                    "type": resource["type"],
                    "attributes": attrs
                }
    
    # Process current state
    for resource in current_state.get("resources", []):
        for instance in resource.get("instances", []):
            attrs = instance.get("attributes", {})
            resource_id = attrs.get("id") or attrs.get("name")
            if resource_id:
                current_resources[resource_id] = {
                    "type": resource["type"],
                    "attributes": attrs
                }
    
    # Find added resources
    for resource_id, details in current_resources.items():
        if resource_id not in prev_resources:
            changes.append({
                "action": "added",
                "id": resource_id,
                "type": details["type"]
            })
    
    # Find removed resources
    for resource_id, details in prev_resources.items():
        if resource_id not in current_resources:
            changes.append({
                "action": "removed",
                "id": resource_id,
                "type": details["type"]
            })
    
    # Find modified resources
    for resource_id, current_details in current_resources.items():
        if resource_id in prev_resources:
            prev_details = prev_resources[resource_id]
            
            # Compare attributes
            modified_attrs = []
            for key, value in current_details["attributes"].items():
                if key in prev_details["attributes"] and prev_details["attributes"][key] != value:
                    modified_attrs.append({
                        "name": key,
                        "old": prev_details["attributes"][key],
                        "new": value
                    })
            
            if modified_attrs:
                changes.append({
                    "action": "modified",
                    "id": resource_id,
                    "type": current_details["type"],
                    "changes": modified_attrs
                })
    
    return changes

def generate_state_change_summary(changes):
    """Generate summary of Terraform state changes"""
    summary = "TERRAFORM STATE CHANGES\n\n"
    
    # Group changes by action
    added = [c for c in changes if c["action"] == "added"]
    removed = [c for c in changes if c["action"] == "removed"]
    modified = [c for c in changes if c["action"] == "modified"]
    
    if added:
        summary += f"ADDED RESOURCES ({len(added)}):\n"
        for resource in added:
            summary += f"+ {resource['type']} {resource['id']}\n"
        summary += "\n"
    
    if removed:
        summary += f"REMOVED RESOURCES ({len(removed)}):\n"
        for resource in removed:
            summary += f"- {resource['type']} {resource['id']}\n"
        summary += "\n"
    
    if modified:
        summary += f"MODIFIED TERRAFORM RESOURCES ({len(modified)}):\n"
        for resource in modified:
            summary += f"~ {resource['type']} {resource['id']}\n"
            for change in resource["changes"]:
                summary += f"  ~ {change['name']}: {change['old']} -> {change['new']}\n"
            summary += "\n"
    
    return summary

def generate_summary(unmanaged_resources, deleted_resources, modified_resources):
    """Generate a simple drift summary"""
    summary = "INFRASTRUCTURE DRIFT SUMMARY\n\n"
    
    if unmanaged_resources:
        summary += f"UNMANAGED RESOURCES ({len(unmanaged_resources)}):\n"
        for resource in unmanaged_resources:
            summary += f"- {resource['type']} {resource['id']}\n"
            user_info = resource.get('created_by', {})
            summary += f"  Created by: {user_info.get('user', 'unknown')} at {user_info.get('time', 'unknown')}\n"
            summary += f"  Region: {user_info.get('region', 'unknown')}\n"
            summary += f"  Event: {user_info.get('event', 'unknown')}\n"
        summary += "\n"
    
    if deleted_resources:
        summary += f"DELETED RESOURCES ({len(deleted_resources)}):\n"
        for resource in deleted_resources:
            summary += f"- {resource['type']} {resource['id']}\n"
            user_info = resource.get('deleted_by', {})
            summary += f"  Deleted by: {user_info.get('user', 'unknown')} at {user_info.get('time', 'unknown')}\n"
            summary += f"  Region: {user_info.get('region', 'unknown')}\n"
            summary += f"  Event: {user_info.get('event', 'unknown')}\n"
        summary += "\n"
    
    if modified_resources:
        summary += f"MODIFIED RESOURCES ({len(modified_resources)}):\n"
        for resource in modified_resources:
            summary += f"- {resource['type']} {resource['id']}\n"
            user_info = resource.get('modified_by', {})
            summary += f"  Modified by: {user_info.get('user', 'unknown')} at {user_info.get('time', 'unknown')}\n"
            summary += f"  Region: {user_info.get('region', 'unknown')}\n"
            summary += f"  Event: {user_info.get('event', 'unknown')}\n"
            for change in resource.get('changes', []):
                summary += f"  • {change.get('attribute', '')}: {change.get('expected', '')} -> {change.get('actual', '')}\n"
        summary += "\n"
    
    return summary