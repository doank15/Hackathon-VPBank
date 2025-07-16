import json
import os
import boto3
from datetime import datetime

# --AWS server client
sns_client = boto3.client('sns')
bedrock_agent_runtime_client = boto3.client('bedrock-agent-runtime')

# Configuration
SNS_TOPIC_ARN = os.environ.get('SNS_TOPIC_ARN')
if not SNS_TOPIC_ARN:
    raise ValueError("SNS_TOPIC_ARN environment variable is not set.")
KNOWLEDGE_BASE_ID = os.environ.get('KNOWLEDGE_BASE_ID')
if not KNOWLEDGE_BASE_ID:
    raise ValueError("KNOWLEDGE_BASE_ID environment variable is not set.")
BEDROCK_MODEL_ARN_FOR_KB = os.environ.get('BEDROCK_MODEL_ARN_FOR_KB')
if not BEDROCK_MODEL_ARN_FOR_KB:
    raise ValueError("BEDROCK_MODEL_ARN_FOR_KB environment variable is not set.")


# help function for bedrock RAG (knowledge base)
def invoke_bedrock_knowledge_base(query_text: str) -> str:
    """
    Invokes a Bedrock Knowledge Base to retrieve relevant information and generate a response.
    Requires KNOWLEDGE_BASE_ID and BEDROCK_MODEL_ARN_FOR_KB to be set as environment variables.
    """
    if not KNOWLEDGE_BASE_ID or not BEDROCK_MODEL_ARN_FOR_KB:
        return "Error: Bedrock Knowledge Base not configured properly in Lambda environment variables."

    print(f"Invoking Bedrock Knowledge Base with query (first 500 chars):\n{query_text[:500]}...")
    try:
        response = bedrock_agent_runtime_client.retrieve_and_generate(
            input={
                'text': query_text
            },
            retrieveAndGenerateConfiguration={
                'type': 'KNOWLEDGE_BASE',
                'knowledgeBaseConfiguration': {
                    'knowledgeBaseId': KNOWLEDGE_BASE_ID,
                    'modelArn': BEDROCK_MODEL_ARN_FOR_KB
                }
            }
        )
        llm_output = response['output']['text']
        print(f"Bedrock response received (first 500 chars):\n{llm_output[:500]}...")
        return llm_output
    except Exception as e:
        print(f"ERROR: Failed to invoke Bedrock Knowledge Base: {e}")
        return f"Error: Could not get detailed explanation from AI. Reason: {str(e)}"

# --- Lambda Handler Function ---
def lambda_handler(event, context):
    """
    Main Lambda function to analyze drift using Bedrock and send SNS notifications.
    Expected 'event' structure should contain detailed drift information.
    """
    print(f"Received drift event:\n{json.dumps(event, indent=2)}")

    # Extract relevant data from the incoming event
    # Ensure your CloudTrail processing Lambda outputs this structure.
    drift_id = event.get('drift_id', f"DRIFT-{datetime.now().strftime('%Y%m%d-%H%M%S')}")
    resource_type = event.get('resource_type', 'N/A')
    resource_id = event.get('resource_id', 'N/A')
    resource_name = event.get('resource_name', 'N/A')
    aws_account_id = event.get('aws_account_id', 'N/A')
    aws_region = event.get('aws_region', 'N/A')
    detected_drift_details = event.get('detected_drift_details', [])
    cloudtrail_event_summary = event.get('cloudtrail_event_summary', {})
    desired_state_snapshot = event.get('desired_state_snapshot', {})
    actual_state_snapshot = event.get('actual_state_snapshot', {})
    change_timestamp = event.get('change_timestamp', datetime.now().isoformat())

    # --- 1. Formulate the Bedrock Query (Prompt Engineering) ---
    # This prompt provides comprehensive context to the LLM for accurate analysis.
    
    drift_details_str = "\n".join([
        f"- Attribute: {d.get('attribute', 'N/A')}, Desired: '{d.get('desired_value', 'N/A')}', Actual: '{d.get('actual_value', 'N/A')}' (Source: {d.get('source', 'Unknown')})"
        for d in detected_drift_details
    ])

    prompt_for_bedrock = f"""
    You are an expert cloud security and DevOps engineer working at VPBank, specializing in AWS infrastructure and Terraform.
    Your task is to analyze the following infrastructure drift, explain its implications, predict potential risks, and provide actionable remediation steps, always referencing VPBank's internal policies and best practices where applicable (retrieved from your knowledge base).

    **Drift Event Details:**
    - Drift ID: {drift_id}
    - Resource Type: {resource_type}
    - Resource ID: {resource_id}
    - Resource Name: {resource_name}
    - AWS Account: {aws_account_id}
    - AWS Region: {aws_region}
    - Time of Change Detection: {change_timestamp}

    **Observed Differences (Drift):**
    {drift_details_str}

    **CloudTrail Event Summary (if available, indicates how the change occurred):**
    ```json
    {json.dumps(cloudtrail_event_summary, indent=2)}
    ```

    **Desired State (from IaC/Terraform snapshot):**
    ```json
    {json.dumps(desired_state_snapshot, indent=2)}
    ```

    **Actual State (Currently deployed AWS snapshot):**
    ```json
    {json.dumps(actual_state_snapshot, indent=2)}
    ```

    **Task Instructions:**
    1.  **Explanation:** Provide a clear, concise, and professional explanation of what the drift is, why it's considered drift, and if inferable from context, how it likely occurred (e.g., manual change, unmanaged script).
    2.  **Predicted Risks:** Explicitly identify and describe the potential risks associated with this specific drift for a banking environment (e.g., security vulnerabilities, compliance breaches, cost increases, performance degradation, operational instability).
    3.  **Remediation Options:** Provide step-by-step instructions for *two* distinct remediation options:
        * **Option A (Revert Drift to Desired IaC):** Detail how to revert the infrastructure back to the desired state defined in Terraform. Include specific AWS Console navigation paths or AWS CLI commands where applicable.
        * **Option B (Update IaC to Formalize Change):** Detail how to update the Terraform code to formalize the current actual state (if it's an intended, but unmanaged, modification). Include specific Terraform commands (`terraform plan`, `terraform apply`) and code snippets if possible.
    4.  **Reference Internal Policies:** Integrate references to VPBank's internal policies or best practices (from the Knowledge Base) when explaining risks or recommending remediation. For example, "This change violates VPBank's [Policy Name] regarding [specific rule]."
    5.  **Format:** Structure your response in clear, readable Markdown format, with bolded headings for "Explanation," "Predicted Risks," and "Remediation Options."

    **Begin your analysis now.**
    """

    # --- 2. Invoke Bedrock Knowledge Base ---
    llm_analysis_output = invoke_bedrock_knowledge_base(prompt_for_bedrock)

    # --- 3. Construct SNS Email ---
    # The LLM's full Markdown output will be the body of the email.
    email_subject = f"DriftGuard ALERT: [{resource_type}] {resource_name} (ID: {resource_id}) - Drift Detected!"
    
    # You can add more fixed introductory text here if desired
    email_body = f"""
    Dear DevOps/SRE Team,

    DriftGuard has detected a critical infrastructure drift event. Please find the detailed AI-generated analysis and remediation options below.

    ---
    **Drift Event Summary:**
    - Drift ID: `{drift_id}`
    - Resource Type: `{resource_type}`
    - Resource Name: `{resource_name}`
    - Resource ID: `{resource_id}`
    - AWS Account ID: `{aws_account_id}`
    - AWS Region: `{aws_region}`
    - Detected At: `{change_timestamp}` (UTC)
    ---

    **AI-Generated Analysis & Remediation:**

    {llm_analysis_output}

    ---
    **Action Required:**
    Please investigate this drift immediately using the provided analysis and perform one of the suggested remediation options to bring the infrastructure back into compliance.

    Best regards,
    The DriftGuard System
    """
    # --- NEW: 3.5 Store Drift Analysis in S3 for Knowledge Base Ingestion ---
    S3_BUCKET_FOR_DRIFT_HISTORY = os.environ.get('S3_BUCKET_FOR_DRIFT_HISTORY') # Define this env var
    if S3_BUCKET_FOR_DRIFT_HISTORY:
        s3_client = boto3.client('s3')
    
        # Consolidate all relevant data into a single dict for storage
        drift_report_for_kb = {
            "drift_id": drift_id,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "resource_name": resource_name,
            "aws_account_id": aws_account_id,
            "aws_region": aws_region,
            "change_timestamp": change_timestamp,
            "detected_drift_details": detected_drift_details,
            "cloudtrail_event_summary": cloudtrail_event_summary,
            "desired_state_snapshot": desired_state_snapshot,
            "actual_state_snapshot": actual_state_snapshot,
            "ai_analysis_markdown": llm_analysis_output, # Store the full AI output
            "report_generated_at": datetime.now().isoformat()
        }
        
        # Define a unique filename for the report
        s3_key = f"drift-reports/{drift_id}.json" # Or .md if you prefer markdown files directly
        
        try:
            s3_client.put_object(
                Bucket=S3_BUCKET_FOR_DRIFT_HISTORY,
                Key=s3_key,
                Body=json.dumps(drift_report_for_kb, indent=2),
                ContentType='application/json' # Or 'text/markdown'
            )
            print(f"Successfully stored drift report to S3 bucket {S3_BUCKET_FOR_DRIFT_HISTORY} at {s3_key}")
            
            # Optional: Trigger Knowledge Base ingestion if needed for immediate indexing
            # This requires an additional Bedrock Agent client or a specific API call.
            # For simplicity, often the KB is set to periodically re-sync its S3 source.
            # If immediate ingestion is critical, you'd need to explore Bedrock KB APIs for "UpdateDataSource"
            # and handle the ingestion job status. For a challenge, periodic sync is usually fine.

        except Exception as e:
            print(f"ERROR: Failed to store drift report to S3 for KB: {e}")
            # Decide if this failure should halt the Lambda or just log

    # --- 4. Publish to SNS ---
    if not SNS_TOPIC_ARN:
        print("ERROR: Cannot send SNS notification. SNS_TOPIC_ARN not configured.")
        return {
            'statusCode': 500,
            'body': json.dumps({'message': 'Configuration Error: SNS Topic ARN missing.'})
        }

    try:
        sns_client.publish(
            TopicArn=SNS_TOPIC_ARN,
            Subject=email_subject,
            Message=email_body
        )
        print(f"Successfully published drift alert to SNS topic: {SNS_TOPIC_ARN}")
    except Exception as e:
        print(f"CRITICAL ERROR: Failed to publish SNS message for drift_id {drift_id}: {e}")
        # Depending on criticality, you might want to re-raise the exception or log to a DLQ
        raise e # Re-raise to indicate a failure in this Lambda's execution

    return {
        'statusCode': 200,
        'body': json.dumps({'message': 'Drift analyzed and notification sent', 'drift_id': drift_id})
    }
