import sys
import os
import json
from unittest.mock import patch, MagicMock

# Add the parent directory to the Python path to allow importing lambda_function
# sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import lambda_function

# --- Mock Environment Variables for Local Testing ---
os.environ['SNS_TOPIC_ARN'] = 'arn:aws:sns:ap-southeast-1:123456789012:test-drift-guard-notifications'
os.environ['KNOWLEDGE_BASE_ID'] = 'TEST_KB_ID'
os.environ['BEDROCK_MODEL_ARN_FOR_KB'] = 'arn:aws:bedrock:ap-southeast-1::foundation-model/anthropic.claude-3-sonnet-20240229'
os.environ['AWS_REGION'] = 'ap-southeast-1'


# --- Example Test Event ---
# This simulates the output from your 'cloudtrailGrep' Lambda
test_drift_event = {
  "drift_id": "test-drift-ec2-instance-type-tag",
  "resource_type": "AWS::EC2::Instance",
  "resource_id": "i-0abcdef1234567890",
  "resource_name": "test-web-server-01",
  "aws_account_id": "123456789012",
  "aws_region": "ap-southeast-1",
  "change_timestamp": "2025-07-15T10:30:00Z",
  "detected_drift_details": [
    {
      "attribute": "InstanceType",
      "desired_value": "t2.micro",
      "actual_value": "t2.medium",
      "source": "Manual AWS Console Change (via RunInstances event)"
    },
    {
      "attribute": "Tags.Environment",
      "desired_value": "Production",
      "actual_value": "Dev",
      "source": "Manual AWS Console Change (via CreateTags event)"
    },
    {
      "attribute": "Tags.NewCustomTag",
      "desired_value": "N/A (not in IaC)",
      "actual_value": "SomeValue",
      "source": "Manual AWS Console Change (via CreateTags event)"
    }
  ],
  "cloudtrail_event_summary": {
    "eventName": "RunInstances",
    "userName": "test-user-dev",
    "eventSource": "ec2.amazonaws.com",
    "sourceIpAddress": "203.0.113.45"
  },
  "desired_state_snapshot": {
    "InstanceType": "t2.micro",
    "Tags": {"Environment": "Production", "Project": "DriftGuard"}
  },
  "actual_state_snapshot": {
    "InstanceType": "t2.medium",
    "Tags": {"Environment": "Dev", "Project": "DriftGuard", "NewCustomTag": "SomeValue"}
  }
}

# --- Mock Bedrock and SNS Clients for Testing ---
# This is crucial to avoid actual AWS calls during local unit testing
# Replace with actual Bedrock/SNS if you want to test live (not recommended for unit tests)
@patch('lambda_function.sns_client')
@patch('lambda_function.bedrock_agent_runtime_client')
def test_lambda_handler(mock_bedrock_client, mock_sns_client):
    print("\n--- Running Lambda Handler Test ---")

    # Configure mock Bedrock client's response
    mock_bedrock_client.retrieve_and_generate.return_value = {
        'output': {
            'text': """
**Explanation:** The EC2 instance 'test-web-server-01' has experienced infrastructure drift. Its instance type was manually changed from `t2.micro` (desired) to `t2.medium` (actual), and its 'Environment' tag was changed from 'Production' to 'Dev', with an additional 'NewCustomTag' added. This indicates unmanaged changes outside of Infrastructure-as-Code.

**Predicted Risks:**
1.  **Cost Increase:** `t2.medium` is more expensive than `t2.micro`.
2.  **Compliance Violation:** Tagging inconsistencies can violate internal governance policies at VPBank.
3.  **Operational Inconsistency:** Unmanaged changes lead to discrepancies between documentation and reality, making troubleshooting difficult.

**Remediation Options:**
**Option A (Revert Drift):**
1.  **Stop Instance:** Use AWS Console -> EC2 -> Instances -> select 'test-web-server-01' -> Instance state -> Stop instance.
2.  **Change Instance Type:** Actions -> Instance settings -> Change instance type -> Select `t2.micro`.
3.  **Manage Tags:** Actions -> Instance settings -> Manage tags -> Change 'Environment' to 'Production', remove 'NewCustomTag'.
4.  **Start Instance:** Instance state -> Start instance.

**Option B (Update IaC):**
1.  **Modify Terraform:** Update `main.tf` (or relevant `.tf` file) for `test-web-server-01` to reflect `instance_type = "t2.medium"` and add the new tag `NewCustomTag = "SomeValue"`. Ensure `Environment` tag is `Dev` if intended.
2.  **Run Plan:** `terraform plan` to review changes.
3.  **Apply Changes:** `terraform apply` to formalize the drift into your IaC.
            """
        }
    }

    # Invoke the lambda handler
    response = lambda_function.lambda_handler(test_drift_event, MagicMock())

    # Assertions
    assert response['statusCode'] == 200
    assert "Drift analyzed and notification sent" in response['body']
    
    # Verify Bedrock client was called correctly
    mock_bedrock_client.retrieve_and_generate.assert_called_once()
    
    # Verify SNS client was called correctly
    mock_sns_client.publish.assert_called_once()
    args, kwargs = mock_sns_client.publish.call_args
    assert kwargs['TopicArn'] == os.environ['SNS_TOPIC_ARN']
    assert "DriftGuard ALERT" in kwargs['Subject']
    assert "Explanation:" in kwargs['Message'] # Check for content from LLM
    assert "Predicted Risks:" in kwargs['Message']
    assert "Remediation Options:" in kwargs['Message']

    print("--- Test Passed Successfully ---")

# Run the test
if __name__ == "__main__":
    test_lambda_handler()