resource "aws_iam_role" "config_lambda" {
  name = "config-listener-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17",
    Statement = [{
      Effect = "Allow",
      Principal = { Service = "lambda.amazonaws.com" },
      Action = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "config_lambda_basic" {
  role       = aws_iam_role.config_lambda.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy" "config_lambda_permissions" {
  name = "config-lambda-permissions"
  role = aws_iam_role.config_lambda.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "cloudtrail:LookupEvents",
          "sns:Publish",
          "sqs:ReceiveMessage",
          "sqs:DeleteMessage",
          "sqs:GetQueueAttributes"
        ]
        Resource = "*"
      }
    ]
  })
}

resource "aws_lambda_function" "config_listener" {
  filename         = "${path.module}/code/config_listener.zip"
  function_name    = "iac-config-listener"
  role             = aws_iam_role.config_lambda.arn
  handler          = "lambda_function_config_audit.lambda_handler"
  runtime          = "python3.10"
  source_code_hash = filebase64sha256("${path.module}/code/config_listener.zip")
  environment {
    variables = {
      SNSTopicARN = var.sns_topic_arn
    }
  }
}


