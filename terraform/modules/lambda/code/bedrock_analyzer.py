import json
import boto3
import os
from datetime import datetime

def lambda_handler(event, context):
    """
    Analyze drift reports using Amazon Bedrock and send human-readable analysis via SNS
    Also save drift reports to S3 for knowledge base ingestion and RAG
    """
    
    # Initialize clients
    bedrock = boto3.client('bedrock-runtime')
    sns = boto3.client('sns')
    s3 = boto3.client('s3')
    model_id = os.environ.get('MODEL_ID', 'anthropic.claude-3-haiku-20240307-v1:0')
    sns_topic = os.environ.get('SNS_TOPIC_ARN')
    history_bucket = os.environ.get('HISTORY_BUCKET', 'drift-history-bucket')
    
    # Extract drift report from event
    drift_report = event.get('drift_report', {})
    
    # Format the drift report for better analysis
    formatted_report = format_drift_report(drift_report)
    
    # Create prompt for Bedrock
    prompt = f"""
You are an Infrastructure Drift Analyzer for AWS resources in a banking environment. You're analyzing a drift report that shows differences between infrastructure defined in Terraform code and actual AWS resources.

The drift report has already been formatted in a specific structure. Your task is to enhance the analysis sections with more detailed insights while maintaining the existing format. Focus on these areas:

1. DRIFT EXPLANATION
   - Provide more context about why these changes matter in a banking environment
   - Explain potential impacts on related systems
   - Identify patterns in the changes that might indicate broader issues

2. RISK ASSESSMENT
   - Expand on security implications specific to banking/financial services
   - Discuss compliance concerns (PCI-DSS, GDPR, etc.) relevant to the changes
   - Analyze operational risks in more detail
   - Provide cost impact assessment if applicable

3. REMEDIATION OPTIONS
   - Enhance the existing remediation options with more detailed steps
   - Add any banking-specific considerations for each option
   - Suggest priority order for addressing multiple issues

4. IMMEDIATE ACTIONS
   - Recommend specific AWS Config rules that should be implemented
   - Suggest improved IAM policies or Service Control Policies
   - Recommend specific monitoring improvements

Drift Report:
{formatted_report}

IMPORTANT: DO NOT change the overall structure of the report. Keep all existing sections and formatting. Only enhance the content within each section with more detailed analysis. Use plain language that both technical and non-technical stakeholders can understand.
"""
    
    try:
        # Call Bedrock with Claude 3 format
        response = bedrock.invoke_model(
            modelId=model_id,
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 2000,
                "temperature": 0.2,  # Lower temperature for more factual responses
                "messages": [
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            })
        )
        
        # Parse response
        result = json.loads(response['body'].read())
        analysis = result['content'][0]['text']
        
        # Send analysis via SNS
        if sns_topic:
            # Create email subject based on drift report
            unmanaged_count = len(drift_report.get('unmanaged_resources', []))
            deleted_count = len(drift_report.get('deleted_resources', []))
            modified_count = len(drift_report.get('modified_resources', []))
            
            # Create a more descriptive subject line with severity icon
            total_changes = unmanaged_count + deleted_count + modified_count
            
            if total_changes > 10 or deleted_count > 5:
                severity = "CRITICAL"
                severity_icon = "🔴"
            elif total_changes > 5:
                severity = "HIGH"
                severity_icon = "🟠"
            elif total_changes > 0:
                severity = "MEDIUM"
                severity_icon = "🟡"
            else:
                severity = "LOW"
                severity_icon = "🟢"
            
            # Get the first resource for the subject line
            primary_resource = None
            if modified_count > 0:
                primary_resource = drift_report.get('modified_resources', [])[0]
                resource_type = "modified"
                status_icon = "🔄"
            elif deleted_count > 0:
                primary_resource = drift_report.get('deleted_resources', [])[0]
                resource_type = "deleted"
                status_icon = "🗑️"
            elif unmanaged_count > 0:
                primary_resource = drift_report.get('unmanaged_resources', [])[0]
                resource_type = "unmanaged"
                status_icon = "➕"
                
            if primary_resource:
                resource_id = primary_resource.get('id', 'Unknown')
                subject = f"{severity_icon} [{severity}] DriftGuard Alert: {status_icon} {resource_type.upper()} {primary_resource.get('type', '')} {resource_id}"
            else:
                subject = f"{severity_icon} [{severity}] DriftGuard Alert: Infrastructure Drift Detected"
            
            # Create email message with analysis
            message = analysis
            
            # Generate a unique drift ID
            drift_id = f"drift-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}"
            timestamp = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
            
            # Try to save to S3 if the bucket exists
            if history_bucket and history_bucket != 'drift-history-bucket':
                try:
                    drift_data = {
                        "drift_id": drift_id,
                        "timestamp": timestamp,
                        "severity": severity,
                        "summary": {
                            "unmanaged_count": unmanaged_count,
                            "deleted_count": deleted_count,
                            "modified_count": modified_count,
                            "total_changes": total_changes
                        },
                        "raw_drift_report": drift_report,
                        "formatted_report": formatted_report,
                        "analysis": analysis
                    }
                    
                    # Save as JSON for structured data access
                    s3.put_object(
                        Bucket=history_bucket,
                        Key=f"drift-history/{drift_id}/drift_data.json",
                        Body=json.dumps(drift_data),
                        ContentType="application/json"
                    )
                    
                    # Save as Markdown for knowledge base ingestion
                    markdown_content = f"# Drift Report: {drift_id}\n\n"
                    markdown_content += f"**Timestamp:** {timestamp}\n\n"
                    markdown_content += f"**Severity:** {severity}\n\n"
                    markdown_content += f"**Summary:** {unmanaged_count} unmanaged, {deleted_count} deleted, {modified_count} modified resources\n\n"
                    markdown_content += "## Drift Report\n\n"
                    markdown_content += formatted_report
                    markdown_content += "\n\n## Analysis\n\n"
                    markdown_content += analysis
                    
                    s3.put_object(
                        Bucket=history_bucket,
                        Key=f"drift-history/{drift_id}/drift_report.md",
                        Body=markdown_content,
                        ContentType="text/markdown"
                    )
                    
                    print(f"Drift report saved to S3: s3://{history_bucket}/drift-history/{drift_id}/")
                except Exception as s3_error:
                    print(f"Warning: Could not save to S3: {str(s3_error)}. Continuing with SNS notification.")
            else:
                print("S3 bucket not configured. Skipping S3 storage.")
                
            # Continue with SNS notification even if S3 storage fails
            
            # Send email notification
            sns.publish(
                TopicArn=sns_topic,
                Subject=subject,
                Message=message
            )
            print(f"Analysis sent to SNS topic: {sns_topic}")
        
        return {
            'statusCode': 200,
            'body': {
                'drift_id': drift_id,
                'analysis': analysis,
                'model_used': model_id,
                'notification_sent': bool(sns_topic),
                's3_location': f"s3://{history_bucket}/drift-history/{drift_id}/"
            }
        }
    except Exception as e:
        error_msg = f"Error analyzing drift: {str(e)}"
        print(error_msg)
        
        # Send error notification
        if sns_topic:
            sns.publish(
                TopicArn=sns_topic,
                Subject="Infrastructure Drift Analysis Error",
                Message=f"Failed to analyze drift report: {error_msg}"
            )
        
        return {
            'statusCode': 500,
            'body': {
                'error': str(e)
            }
        }

def format_drift_report(drift_report):
    """Format the drift report in the requested email format"""
    # Generate a unique drift ID
    drift_id = f"drift-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}"
    timestamp = drift_report.get('timestamp', datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"))
    
    # Start with the email header
    formatted = "Dear DevOps/SRE Team,\n\n"
    formatted += "DriftGuard has detected infrastructure drift that requires immediate attention.\n\n"
    formatted += "---\n"
    
    # Count resources with drift
    unmanaged = drift_report.get('unmanaged_resources', [])
    deleted = drift_report.get('deleted_resources', [])
    modified = drift_report.get('modified_resources', [])
    
    # Get the first resource for the summary (prioritize modified, then deleted, then unmanaged)
    primary_resource = None
    if modified:
        primary_resource = modified[0]
        drift_type = "MODIFIED"
    elif deleted:
        primary_resource = deleted[0]
        drift_type = "DELETED"
    elif unmanaged:
        primary_resource = unmanaged[0]
        drift_type = "UNMANAGED"
    
    # If we have a primary resource, create a summary
    if primary_resource:
        resource_type = primary_resource.get('type', 'Unknown')
        resource_id = primary_resource.get('id', 'Unknown')
        aws_resource_type = f"AWS::{resource_type.replace('aws_', '').upper()}::INSTANCE"
        
        # Get region and user info
        if drift_type == "MODIFIED":
            user_info = primary_resource.get('modified_by', {})
        elif drift_type == "DELETED":
            user_info = primary_resource.get('deleted_by', {})
        else:  # UNMANAGED
            user_info = primary_resource.get('created_by', {})
            
        region = user_info.get('region', 'unknown')
        
        # Calculate severity based on counts
        total_changes = len(unmanaged) + len(deleted) + len(modified)
        if total_changes > 10 or len(deleted) > 5:
            severity_icon = "🔴🔴🔴 CRITICAL 🔴🔴🔴"
        elif total_changes > 5:
            severity_icon = "🟠🟠 HIGH 🟠🟠"
        elif total_changes > 0:
            severity_icon = "🟡 MEDIUM 🟡"
        else:
            severity_icon = "🟢 LOW 🟢"
            
        # Create a summary of all resources in drift state in a format compatible with email
        formatted += f"## {severity_icon} **Drift Event Summary**\n\n"
        
        # Add unmanaged resources to the summary
        if unmanaged:
            formatted += "### 🆕 **UNMANAGED RESOURCES:**\n\n"
            for resource in unmanaged:
                resource_type = resource.get('type', 'Unknown')
                resource_id = resource.get('id', 'Unknown')
                created_by = resource.get('created_by', {})
                user = created_by.get('user', 'unknown')
                event = created_by.get('event', 'unknown')
                time = created_by.get('time', 'unknown')
                region = created_by.get('region', 'unknown')
                formatted += f"- **Resource Name: `{resource_type}`**\n"
                formatted += f"  **Resource ID: `{resource_id}`**\n"
                formatted += f"  **Status: `UNMANAGED`**\n"
                formatted += f"  Region: {region}\n"
                formatted += f"  Event: {event}\n"
                formatted += f"  Created by: {user}\n"
                formatted += f"  Timestamp: {time}\n\n"
        
        # Add deleted resources to the summary
        if deleted:
            formatted += "### 🗑️ **DELETED RESOURCES:**\n\n"
            for resource in deleted:
                resource_type = resource.get('type', 'Unknown')
                resource_id = resource.get('id', 'Unknown')
                deleted_by = resource.get('deleted_by', {})
                user = deleted_by.get('user', 'unknown')
                event = deleted_by.get('event', 'unknown')
                time = deleted_by.get('time', 'unknown')
                region = deleted_by.get('region', 'unknown')
                formatted += f"- **Resource Name: `{resource_type}`**\n"
                formatted += f"  **Resource ID: `{resource_id}`**\n"
                formatted += f"  **Status: `DELETED`**\n"
                formatted += f"  Region: {region}\n"
                formatted += f"  Event: {event}\n"
                formatted += f"  Deleted by: {user}\n"
                formatted += f"  Timestamp: {time}\n\n"
        
        # Add modified resources to the summary
        if modified:
            formatted += "### 🔄 **MODIFIED RESOURCES:**\n\n"
            for resource in modified:
                resource_type = resource.get('type', 'Unknown')
                resource_id = resource.get('id', 'Unknown')
                modified_by = resource.get('modified_by', {})
                user = modified_by.get('user', 'unknown')
                event = modified_by.get('event', 'unknown')
                time = modified_by.get('time', 'unknown')
                region = modified_by.get('region', 'unknown')
                formatted += f"- **Resource Name: `{resource_type}`**\n"
                formatted += f"  **Resource ID: `{resource_id}`**\n"
                formatted += f"  **Status: `MODIFIED`**\n"
                formatted += f"  Region: {region}\n"
                formatted += f"  Event: {event}\n"
                formatted += f"  Modified by: {user}\n"
                formatted += f"  Timestamp: {time}\n\n"
        
        formatted += f"\n**Drift ID:** `{drift_id}`\n"
        formatted += f"**Account:** `123456789012`\n"  # Placeholder account ID
        formatted += f"**Detected:** `{timestamp}` UTC\n\n"
        formatted += "---\n"
    
    # AI Analysis section
    formatted += "## 🔍 **AI Analysis & Remediation**\n\n\n"
    
    # Detailed drift analysis
    formatted += "Here is a detailed drift analysis for the detected infrastructure changes:\n\n"
    
    # 1. Drift Explanation
    formatted += "## 1. Drift Explanation\n\n"
    
    # Add details about each type of drift
    if unmanaged:
        formatted += "- **Unmanaged Resources:** The following resources exist in AWS but are not managed by Terraform:\n"
        for resource in unmanaged:
            resource_type = resource.get('type', 'Unknown')
            resource_id = resource.get('id', 'Unknown')
            created_by = resource.get('created_by', {})
            user = created_by.get('user', 'unknown')
            event = created_by.get('event', 'unknown')
            formatted += f"  - {resource_type} `{resource_id}` was created via `{event}` by `{user}`\n"
        formatted += "\n"
    
    if deleted:
        formatted += "- **Deleted Resources:** The following resources are defined in Terraform but have been deleted from AWS:\n"
        for resource in deleted:
            resource_type = resource.get('type', 'Unknown')
            resource_id = resource.get('id', 'Unknown')
            deleted_by = resource.get('deleted_by', {})
            user = deleted_by.get('user', 'unknown')
            event = deleted_by.get('event', 'unknown')
            formatted += f"  - {resource_type} `{resource_id}` was deleted via `{event}` by `{user}`\n"
        formatted += "\n"
    
    if modified:
        formatted += "- **Modified Resources:** The following resources have been modified outside of Terraform:\n"
        for resource in modified:
            resource_type = resource.get('type', 'Unknown')
            resource_id = resource.get('id', 'Unknown')
            modified_by = resource.get('modified_by', {})
            user = modified_by.get('user', 'unknown')
            event = modified_by.get('event', 'unknown')
            formatted += f"  - {resource_type} `{resource_id}` was modified via `{event}` by `{user}`\n"
            
            # Add details about the changes
            changes = resource.get('changes', [])
            if changes:
                for change in changes:
                    attribute = change.get('attribute', '')
                    expected = change.get('expected', '')
                    actual = change.get('actual', '')
                    formatted += f"    - The `{attribute}` was changed from `{expected}` (desired) to `{actual}` (actual)\n"
        formatted += "\n"
    
    formatted += "This is considered drift from the desired infrastructure state defined in IaC. "
    formatted += "The likely cause is direct manual changes through the AWS Console by a user.\n\n"
    formatted += "For a banking environment, these changes could impact security groups, auto-scaling rules, monitoring alerts, "
    formatted += "and other dependencies. The changes pose operational, security, and compliance risks.\n\n"
    
    # 2. Risk Assessment
    formatted += "## 2. Risk Assessment\n\n"
    formatted += "- **Security**: Unauthorized changes could bypass security controls like VPC Network ACLs, IAM policies, etc. "
    formatted += "Mismatched configurations could break security group rules.\n\n"
    formatted += "- **Compliance**: Drift from approved configurations could violate regulatory requirements for banking environments.\n\n"
    formatted += "- **Operations**: Dependency failures from unexpected changes. May increase costs or impact performance.\n\n"
    formatted += "- **Cost**: Unmanaged resources or modified configurations could lead to unexpected costs.\n\n"
    
    # 3. Remediation Options
    formatted += "## 3. Remediation Options\n\n"
    
    # Option A: Revert to IaC State
    formatted += "### Option A: Revert to IaC State\n\n"
    formatted += "**AWS Console Steps:**\n\n"
    
    if modified:
        formatted += "1. Review the modified resources in the AWS Console\n\n"
        formatted += "2. Revert the changes manually or proceed with Terraform commands\n\n"
    if unmanaged:
        formatted += "3. Consider removing unmanaged resources if they're not needed\n\n"
    if deleted:
        formatted += "4. Be aware that deleted resources will be recreated\n\n"
    
    formatted += "**Terraform Commands:**\n\n"
    formatted += "```\n"
    formatted += "# Review what changes will be made\n"
    formatted += "terraform plan -out=tfplan\n\n"
    formatted += "# Apply the changes to revert to the IaC state\n"
    formatted += "terraform apply tfplan\n\n"
    formatted += "# Verify resources match IaC state\n"
    formatted += "```\n\n"
    
    # Option B: Update IaC to Match Current State
    formatted += "### Option B: Update IaC to Match Current State\n\n"
    formatted += "**Terraform Changes:**\n\n"
    
    if unmanaged:
        formatted += "- For unmanaged resources, import them into Terraform:\n\n"
        formatted += "```\n"
        for resource in unmanaged:
            resource_type = resource.get('type', 'Unknown')
            resource_id = resource.get('id', 'Unknown')
            tf_resource_type = get_terraform_resource_type(resource_type)
            formatted += f"# Import {resource_type} {resource_id}\n"
            formatted += f"terraform import {tf_resource_type}.{resource_id.replace('-', '_')} {resource_id}\n\n"
            formatted += f"# Add to your Terraform configuration:\n"
            formatted += generate_terraform_code(resource_type, resource_id) + "\n\n"
        formatted += "```\n\n"
    
    if modified:
        formatted += "- For modified resources, update your Terraform code:\n\n"
        formatted += "```\n"
        for resource in modified:
            resource_type = resource.get('type', 'Unknown')
            resource_id = resource.get('id', 'Unknown')
            tf_resource_type = get_terraform_resource_type(resource_type)
            changes = resource.get('changes', [])
            if changes:
                formatted += f"# Update {resource_type} {resource_id} in your Terraform configuration:\n"
                formatted += f"resource \"{tf_resource_type}\" \"{resource_id.replace('-', '_')}\" {{\n"
                for change in changes:
                    attribute = change.get('attribute', '')
                    actual = change.get('actual', '')
                    if isinstance(actual, str) and not actual.isnumeric():
                        formatted += f"  {attribute} = \"{actual}\"\n"
                    else:
                        formatted += f"  {attribute} = {actual}\n"
                formatted += "  # other attributes remain the same\n"
                formatted += "}\n\n"
        formatted += "```\n\n"
    
    if deleted:
        formatted += "- For deleted resources, remove them from Terraform:\n\n"
        formatted += "```\n"
        for resource in deleted:
            resource_type = resource.get('type', 'Unknown')
            resource_id = resource.get('id', 'Unknown')
            tf_resource_type = get_terraform_resource_type(resource_type)
            formatted += f"# Remove {resource_type} {resource_id} from your Terraform state:\n"
            formatted += f"terraform state rm {tf_resource_type}.{resource_id.replace('-', '_')}\n\n"
            formatted += f"# Also remove the resource block from your Terraform files\n\n"
        formatted += "```\n\n"
    
    formatted += "**Process:**\n\n"
    formatted += "```\n"
    formatted += "terraform plan -out=tfplan\n\n"
    formatted += "terraform apply tfplan\n\n"
    formatted += "# Commit changes, raise PR, go through CI/CD process\n\n"
    formatted += "# Update documentation to match new configuration\n"
    formatted += "```\n\n"
    
    # 4. Immediate Actions
    formatted += "## 4. Immediate Actions\n\n"
    formatted += "- Enable AWS Config Rules to detect/alert on configuration changes\n\n"
    formatted += "- Setup drift detection to run daily and alert on any deviations\n\n"
    formatted += "- Educate users on proper change management procedures\n\n"
    formatted += "- Lock down IAM permissions to restrict unauthorized modifications\n\n"
    formatted += "Please let me know if you need any clarification or have additional questions!\n\n"
    
    # Footer
    formatted += "---\n"
    formatted += "**This is an automated alert from DriftGuard System** \n"
    formatted += "For technical issues, contact the DevOps team.\n"
    
    return formatted

def get_terraform_resource_type(aws_resource_type):
    """Convert AWS resource type to Terraform resource type"""
    mapping = {
        'EC2': 'aws_instance',
        'S3': 'aws_s3_bucket',
        'IAM': 'aws_iam_user',
        'RDS': 'aws_db_instance',
        'aws_instance': 'aws_instance',
        'aws_s3_bucket': 'aws_s3_bucket',
        'aws_iam_user': 'aws_iam_user',
        'aws_db_instance': 'aws_db_instance',
        'aws_vpc': 'aws_vpc',
        'aws_subnet': 'aws_subnet'
    }
    return mapping.get(aws_resource_type, 'aws_resource')

def generate_terraform_code(resource_type, resource_id):
    """Generate example Terraform code for a resource"""
    tf_resource_type = get_terraform_resource_type(resource_type)
    resource_name = resource_id.replace('-', '_')
    
    if tf_resource_type == 'aws_instance':
        return f"resource \"aws_instance\" \"{resource_name}\" {{\n  ami           = \"ami-12345678\"  # Replace with actual AMI ID\n  instance_type = \"t3.micro\"     # Replace with actual instance type\n  tags = {{\n    Name = \"{resource_id}\"\n  }}\n}}"
    
    elif tf_resource_type == 'aws_s3_bucket':
        return f"resource \"aws_s3_bucket\" \"{resource_name}\" {{\n  bucket = \"{resource_id}\"\n  tags = {{\n    Name = \"{resource_id}\"\n  }}\n}}"
    
    elif tf_resource_type == 'aws_iam_user':
        return f"resource \"aws_iam_user\" \"{resource_name}\" {{\n  name = \"{resource_id}\"\n  tags = {{\n    Name = \"{resource_id}\"\n  }}\n}}"
    
    elif tf_resource_type == 'aws_db_instance':
        return f"resource \"aws_db_instance\" \"{resource_name}\" {{\n  identifier           = \"{resource_id}\"\n  allocated_storage    = 20  # Replace with actual storage\n  engine               = \"mysql\"  # Replace with actual engine\n  instance_class       = \"db.t3.micro\"  # Replace with actual class\n  # Add other required attributes\n}}"
    
    elif tf_resource_type == 'aws_vpc':
        return f"resource \"aws_vpc\" \"{resource_name}\" {{\n  cidr_block = \"10.0.0.0/16\"  # Replace with actual CIDR\n  tags = {{\n    Name = \"{resource_id}\"\n  }}\n}}"
    
    elif tf_resource_type == 'aws_subnet':
        return f"resource \"aws_subnet\" \"{resource_name}\" {{\n  vpc_id     = \"vpc-12345678\"  # Replace with actual VPC ID\n  cidr_block = \"10.0.1.0/24\"  # Replace with actual CIDR\n  tags = {{\n    Name = \"{resource_id}\"\n  }}\n}}"
    
    else:
        return f"resource \"{tf_resource_type}\" \"{resource_name}\" {{\n  # Add required attributes for {resource_type}\n  # Refer to Terraform documentation\n}}"