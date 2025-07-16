resource "aws_lambda_function" "config_drift" {
  filename         = "${path.module}/code/config_drift.zip"
  function_name    = "iac-config-drift-detector"
  role             = aws_iam_role.drift_lambda.arn
  handler          = "lambda_function_config_drift.lambda_handler"
  runtime          = "python3.10"
  timeout          = 30
  source_code_hash = filebase64sha256("${path.module}/code/config_drift.zip")
  environment {
    variables = {
      TFSTATE_BUCKET = var.s3_bucket
      SNS_TOPIC_ARN = var.sns_topic_arn
    }
  }
}

