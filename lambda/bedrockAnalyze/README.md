# Bedrock Analyzer Lambda Function

This Lambda function is a core component of the DriftGuard solution. Its primary responsibility is to:
1.  Receive structured drift detection events from the `cloudtrailGrep` Lambda (or another source).
2.  Utilize Amazon Bedrock (specifically its Knowledge Base and Foundation Models) to analyze the detected drift.
3.  Generate a human-readable explanation, predict potential risks, and propose actionable remediation steps in natural language.
4.  Send a comprehensive alert email via Amazon SNS to the Ops/DevOps team.

## Input Event Structure

This Lambda expects an incoming JSON event with the following structure (example):

```json
{
  "drift_id": "unique-drift-id-12345",
  "resource_type": "AWS::EC2::Instance",
  "resource_id": "i-0abcdef1234567890",
  "resource_name": "web-server-prod-01",
  "aws_account_id": "123456789012",
  "aws_region": "ap-southeast-1",
  "change_timestamp": "2025-07-15T10:30:00Z",
  "detected_drift_details": [
    {
      "attribute": "InstanceType",
      "desired_value": "t3.medium",
      "actual_value": "t3.large",
      "source": "Manual AWS Console Change"
    },
    {
      "attribute": "Tags.Environment",
      "desired_value": "Production",
      "actual_value": "Prod",
      "source": "CloudTrail Event"
    }
  ],
  "cloudtrail_event_summary": {
    "eventName": "RunInstances",
    "userName": "manual_user_via_console",
    "eventSource": "ec2.amazonaws.com",
    "sourceIpAddress": "X.X.X.X"
  },
  "desired_state_snapshot": {
    "InstanceType": "t3.medium",
    "Tags": {"Environment": "Production", "Service": "WebServer"}
  },
  "actual_state_snapshot": {
    "InstanceType": "t3.large",
    "Tags": {"Environment": "Prod", "Service": "WebServer", "Owner": "Admin"}
  }
}