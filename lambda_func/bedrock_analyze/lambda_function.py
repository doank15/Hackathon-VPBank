import json
import os
import boto3
from datetime import datetime

# --AWS server client
sns_client = boto3.client('sns')
bedrock_agent_runtime_client = boto3.client('bedrock-agent-runtime')
# Client for direct LLM invocation if KB fails
bedrock_runtime_client = boto3.client('bedrock-runtime')

# Configuration
SNS_TOPIC_ARN = os.environ.get('SNS_TOPIC_ARN', "arn:aws:sns:ap-southeast-1:034362060101:bedrock-drift-analyze")
KNOWLEDGE_BASE_ID = os.environ.get('KNOWLEDGE_BASE_ID', "HZDWN3EYQP")

# FIXED: Use inference profile ARN instead of model ARN for KB
BEDROCK_MODEL_ARN_FOR_KB = os.environ.get('BEDROCK_MODEL_ARN_FOR_KB', 
    "arn:aws:bedrock:ap-southeast-1:034362060101:inference-profile/anthropic.claude-3-sonnet-20240229-v1:0")
# "arn:aws:bedrock:ap-southeast-1::foundation-model/anthropic.claude-v2")

# FIXED: Use inference profile ID instead of model ID for direct invocation
BEDROCK_MODEL_ID_FOR_DIRECT_INVOKE = os.environ.get('BEDROCK_MODEL_ID_FOR_DIRECT_INVOKE', 
    "anthropic.claude-v2")

def invoke_bedrock_knowledge_base(query_text: str) -> str:
    """
    Invokes a Bedrock Knowledge Base to retrieve relevant information and generate a response.
    Enhanced error handling and fallback mechanisms.
    """
    kb_error_message = ""
    llm_output_from_kb = None

    # Attempt to invoke with Knowledge Base first
    if KNOWLEDGE_BASE_ID and BEDROCK_MODEL_ARN_FOR_KB:
        try:
            print(f"Attempting to invoke Bedrock Knowledge Base with ID: {KNOWLEDGE_BASE_ID}, Model ARN: {BEDROCK_MODEL_ARN_FOR_KB}")
            
            response = bedrock_agent_runtime_client.retrieve_and_generate(
                input={
                    'text': query_text
                },
                retrieveAndGenerateConfiguration={
                    'type': 'KNOWLEDGE_BASE',
                    'knowledgeBaseConfiguration': {
                        'knowledgeBaseId': KNOWLEDGE_BASE_ID,
                        'modelArn': BEDROCK_MODEL_ARN_FOR_KB,
                        'retrievalConfiguration': {
                            'vectorSearchConfiguration': {
                                'numberOfResults': 3,
                                'overrideSearchType': 'HYBRID'
                            }
                        },
                        'generationConfiguration': {
                            'inferenceConfig': {
                                'textInferenceConfig': {
                                    'maxTokens': 4000,
                                    'temperature': 0.1
                                }
                            }
                        }
                    }
                }
            )
            llm_output_from_kb = response['output']['text']
            print("Successfully retrieved response from Knowledge Base")
            return llm_output_from_kb
            
        except Exception as e:
            error_msg = str(e)
            print(f"ERROR: Failed to invoke Bedrock Knowledge Base: {error_msg}")
            
            if "AccessDeniedException" in error_msg:
                kb_error_message = f"""
**Knowledge Base Error:** Access denied to Knowledge Base or inference profile.
Error details: `{error_msg}`
Please verify:
1. Knowledge Base ID ({KNOWLEDGE_BASE_ID}) is correct and active
2. Inference Profile ARN ({BEDROCK_MODEL_ARN_FOR_KB}) is valid
3. IAM role has `bedrock:RetrieveAndGenerate` and `bedrock:GetInferenceProfile` permissions

Falling back to direct AI analysis...

---
"""
            else:
                kb_error_message = f"""
**Knowledge Base Error:** Unable to retrieve information from Knowledge Base.
Error: `{error_msg}`
Falling back to direct AI analysis...

---
"""
    else:
        kb_error_message = """
**Configuration Warning:** Bedrock Knowledge Base is not fully configured.
Using direct AI analysis without internal policy context.

---
"""
        print("WARNING: Bedrock Knowledge Base is not fully configured")

    # Fallback to direct LLM invocation
    if BEDROCK_MODEL_ID_FOR_DIRECT_INVOKE:
        try:
            print(f"Attempting direct LLM invocation with model ID: {BEDROCK_MODEL_ID_FOR_DIRECT_INVOKE}")
            
            body = json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 4000,
                "temperature": 0.1,
                "system": "You are an expert cloud security and DevOps engineer specializing in AWS infrastructure drift analysis. Provide detailed, actionable insights for banking environments.",
                "messages": [
                    {
                        "role": "user",
                        "content": query_text
                    }
                ]
            })
            
            response = bedrock_runtime_client.invoke_model(
                modelId=BEDROCK_MODEL_ID_FOR_DIRECT_INVOKE,
                contentType="application/json",
                accept="application/json",
                body=body
            )
            
            response_body = json.loads(response['body'].read())
            direct_llm_output = response_body['content'][0]['text']
            
            print("Successfully got response from direct LLM invocation")
            return kb_error_message + direct_llm_output
            
        except Exception as e:
            error_msg = str(e)
            print(f"CRITICAL ERROR: Failed to invoke Bedrock model directly: {error_msg}")
            
            error_suggestion = """
Please check:
1. Model ID is valid (e.g., anthropic.claude-3-sonnet-20240229-v1:0)
2. IAM role has `bedrock:InvokeModel` permissions for the model
3. Bedrock service quotas and region availability
"""
            
            return f"""
{kb_error_message}
**CRITICAL ERROR:** AI analysis could not be generated.
Error: `{error_msg}`

{error_suggestion}

---
**Manual Analysis Required:** Please manually review the drift details and take appropriate action.
"""
    else:
        return f"""
{kb_error_message}
**CRITICAL ERROR:** No AI model configured for analysis.
Please set `BEDROCK_MODEL_ID_FOR_DIRECT_INVOKE` environment variable.

---
**Manual Analysis Required:** Please manually review the drift details and take appropriate action.
"""

def lambda_handler(event, context):
    """
    Main Lambda function to analyze drift using Bedrock and send SNS notifications.
    Enhanced error handling and logging.
    """
    print(f"Received drift event:\n{json.dumps(event, indent=2)}")

    # Extract relevant data from the incoming event
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

    # Format drift details for better readability
    drift_details_str = "\n".join([
        f"- **{d.get('attribute', 'N/A')}**: Desired=`{d.get('desired_value', 'N/A')}`, Actual=`{d.get('actual_value', 'N/A')}` (Source: {d.get('source', 'Unknown')})"
        for d in detected_drift_details
    ])

    # Enhanced prompt with better structure
    prompt_for_bedrock = f"""
You are an expert cloud security and DevOps engineer at VPBank, specializing in AWS infrastructure drift analysis.

**DRIFT ANALYSIS REQUEST:**

**Resource Information:**
- Drift ID: {drift_id}
- Resource Type: {resource_type}
- Resource ID: {resource_id}
- Resource Name: {resource_name}
- AWS Account: {aws_account_id}
- AWS Region: {aws_region}
- Detection Time: {change_timestamp}

**Detected Changes:**
{drift_details_str}

**CloudTrail Context:**
```json
{json.dumps(cloudtrail_event_summary, indent=2)}
```

**Infrastructure States:**
**Desired State (IaC):**
```json
{json.dumps(desired_state_snapshot, indent=2)}
```

**Actual State (AWS):**
```json
{json.dumps(actual_state_snapshot, indent=2)}
```

**REQUIRED ANALYSIS:**

## 1. **Drift Explanation**
- What changed and why this is considered drift
- Likely cause of the change (manual, script, automation failure)
- Impact assessment for banking environment

## 2. **Risk Assessment**
- Security implications
- Compliance concerns
- Operational risks
- Cost impact

## 3. **Remediation Options**

### Option A: Revert to IaC State
- Step-by-step AWS Console/CLI commands
- Terraform commands to restore desired state
- Verification steps

### Option B: Update IaC to Match Current State
- Required Terraform code changes
- terraform plan/apply process
- Documentation updates needed

## 4. **Immediate Actions**
- Urgent steps required
- Monitoring recommendations
- Prevention measures

Please provide comprehensive analysis in clear markdown format.
"""

    # Invoke Bedrock for analysis
    try:
        llm_analysis_output = invoke_bedrock_knowledge_base(prompt_for_bedrock)
    except Exception as e:
        print(f"Unexpected error in Bedrock analysis: {e}")
        llm_analysis_output = f"""
**SYSTEM ERROR:** An unexpected error occurred during drift analysis.
Error: `{str(e)}`

**Manual Review Required:** Please investigate the following drift manually:
- Resource: {resource_name} ({resource_id})
- Type: {resource_type}
- Changes: {drift_details_str}
"""

    # Construct enhanced SNS email
    email_subject = f"🚨 DriftGuard Alert: {resource_name} ({resource_type}) - {drift_id}"
    
    email_body = f"""
Dear DevOps/SRE Team,

DriftGuard has detected infrastructure drift that requires immediate attention.

---
## 📋 **Drift Event Summary**
- **Drift ID:** `{drift_id}`
- **Resource:** `{resource_name}` ({resource_id})
- **Type:** `{resource_type}`
- **Account:** `{aws_account_id}`
- **Region:** `{aws_region}`
- **Detected:** `{change_timestamp}` UTC

---
## 🔍 **AI Analysis & Remediation**

{llm_analysis_output}

---
**This is an automated alert from DriftGuard System**  
For technical issues, contact the DevOps team.
"""

    # Store drift analysis in S3 for Knowledge Base
    S3_BUCKET_FOR_DRIFT_HISTORY = os.environ.get('S3_BUCKET_FOR_DRIFT_HISTORY', "statetf-bucket")
    if S3_BUCKET_FOR_DRIFT_HISTORY:
        try:
            s3_client = boto3.client('s3')
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
                "ai_analysis_markdown": llm_analysis_output,
                "report_generated_at": datetime.now().isoformat()
            }
            
            s3_key = f"drift-reports/{datetime.now().strftime('%Y/%m/%d')}/{drift_id}.json"
            
            s3_client.put_object(
                Bucket=S3_BUCKET_FOR_DRIFT_HISTORY,
                Key=s3_key,
                Body=json.dumps(drift_report_for_kb, indent=2),
                ContentType='application/json'
            )
            print(f"Drift report stored to S3: s3://{S3_BUCKET_FOR_DRIFT_HISTORY}/{s3_key}")
            
        except Exception as e:
            print(f"Warning: Failed to store drift report to S3: {e}")

    # Publish to SNS
    try:
        sns_client.publish(
            TopicArn=SNS_TOPIC_ARN,
            Subject=email_subject,
            Message=email_body
        )
        print(f"Successfully published drift alert to SNS: {SNS_TOPIC_ARN}")
        
    except Exception as e:
        print(f"CRITICAL ERROR: Failed to publish SNS message: {e}")
        raise e

    return {
        'statusCode': 200,
        'body': json.dumps({
            'message': 'Drift analyzed and notification sent successfully',
            'drift_id': drift_id,
            'analysis_status': 'completed'
        })
    }