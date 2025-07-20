# EventBridge rule for AWS Config changes
resource "aws_cloudwatch_event_rule" "config_changes" {
  name        = "config-drift-changes"
  description = "Capture AWS Config configuration changes"

  event_pattern = jsonencode({
    "source": ["aws.config"],
    "detail-type": ["Config Configuration Item Change"],
    "detail": {
      "messageType": ["ConfigurationItemChangeNotification"],
      "configurationItem": {
        "resourceType": [
          "AWS::EC2::Instance",
          "AWS::S3::Bucket",
          "AWS::RDS::DBInstance",
          "AWS::IAM::User",
          "AWS::EC2::VPC",
          "AWS::EC2::Subnet",
          "AWS::Lambda::Function",
          "AWS::DynamoDB::Table"
        ]
      }
    }
  })
}

# EventBridge target for Lambda
resource "aws_cloudwatch_event_target" "config_lambda" {
  rule      = aws_cloudwatch_event_rule.config_changes.name
  target_id = "ConfigDriftLambda"
  arn       = var.lambda_arn
}

# EventBridge rule for CloudTrail API calls
resource "aws_cloudwatch_event_rule" "cloudtrail_api_calls" {
  name        = "cloudtrail-api-calls"
  description = "Capture important CloudTrail API calls"

  event_pattern = jsonencode({
    "source": ["aws.cloudtrail"],
    "detail-type": ["AWS API Call via CloudTrail"],
    "detail": {
      "eventSource": [
        "ec2.amazonaws.com",
        "s3.amazonaws.com",
        "rds.amazonaws.com",
        "iam.amazonaws.com",
        "lambda.amazonaws.com",
        "dynamodb.amazonaws.com"
      ],
      "eventName": [
        "RunInstances",
        "TerminateInstances",
        "ModifyInstanceAttribute",
        "CreateBucket",
        "DeleteBucket",
        "PutBucketPolicy",
        "CreateDBInstance",
        "DeleteDBInstance",
        "ModifyDBInstance",
        "CreateUser",
        "DeleteUser",
        "UpdateUser",
        "CreateFunction",
        "DeleteFunction",
        "UpdateFunctionConfiguration",
        "CreateTable",
        "DeleteTable",
        "UpdateTable"
      ]
    }
  })
}

# EventBridge target for CloudTrail API calls
resource "aws_cloudwatch_event_target" "cloudtrail_lambda" {
  rule      = aws_cloudwatch_event_rule.cloudtrail_api_calls.name
  target_id = "CloudTrailApiCallsLambda"
  arn       = var.lambda_arn
}

# EventBridge rule for S3 state file changes
resource "aws_cloudwatch_event_rule" "s3_state_changes" {
  name        = "s3-state-changes"
  description = "Capture S3 state file changes"

  event_pattern = jsonencode({
    "source": ["aws.s3"],
    "detail-type": ["Object Created"],
    "detail": {
      "bucket": {
        "name": [var.s3_bucket]
      },
      "object": {
        "key": [{
          "suffix": ".tfstate"
        }]
      }
    }
  })
}

# EventBridge target for S3 state changes
resource "aws_cloudwatch_event_target" "s3_state_lambda" {
  rule      = aws_cloudwatch_event_rule.s3_state_changes.name
  target_id = "S3StateChangesLambda"
  arn       = var.lambda_arn
}

# EventBridge scheduled rule to run drift check every 5 minutes
resource "aws_cloudwatch_event_rule" "scheduled_drift_check" {
  name                = "scheduled-drift-check"
  description         = "Run drift check every 5 minutes"
  schedule_expression = "rate(5 minutes)"
}

# EventBridge target for scheduled drift check
resource "aws_cloudwatch_event_target" "scheduled_drift_lambda" {
  rule      = aws_cloudwatch_event_rule.scheduled_drift_check.name
  target_id = "ScheduledDriftCheckLambda"
  arn       = var.lambda_arn
}

# Lambda permission for EventBridge to invoke Lambda
resource "aws_lambda_permission" "config_invoke" {
  statement_id  = "AllowConfigEventsInvoke"
  action        = "lambda:InvokeFunction"
  function_name = var.lambda_arn
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.config_changes.arn
}

resource "aws_lambda_permission" "cloudtrail_invoke" {
  statement_id  = "AllowCloudTrailEventsInvoke"
  action        = "lambda:InvokeFunction"
  function_name = var.lambda_arn
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.cloudtrail_api_calls.arn
}

resource "aws_lambda_permission" "s3_state_invoke" {
  statement_id  = "AllowS3StateEventsInvoke"
  action        = "lambda:InvokeFunction"
  function_name = var.lambda_arn
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.s3_state_changes.arn
}

resource "aws_lambda_permission" "scheduled_invoke" {
  statement_id  = "AllowScheduledInvoke"
  action        = "lambda:InvokeFunction"
  function_name = var.lambda_arn
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.scheduled_drift_check.arn
}