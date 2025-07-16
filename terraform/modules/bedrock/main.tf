resource "aws_iam_role" "bedrock_agent_role" {
  name = "bedrock_agent_execution_role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17",
    Statement = [{
      Effect = "Allow",
      Principal = {
        Service = "lambda.amazonaws.com"
      },
      Action = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_policy" "bedrock_agent_policy" {
  name = "bedrock_agent_permissions"

  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Effect = "Allow",
        Action = [
          "cloudtrail:LookupEvents",
          "s3:GetObject"
        ],
        Resource = "*"
      },
      {
        Effect = "Allow",
        Action = [
          "lambda:InvokeFunction"
        ],
        Resource = "*"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "attach_agent_policy" {
  role       = aws_iam_role.bedrock_agent_role.name
  policy_arn = aws_iam_policy.bedrock_agent_policy.arn
}

# Lambda function that serves as an Action Group handler
data "archive_file" "lambda_zip" {
  type        = "zip"
  source_dir  = "../lambda_function/"
  output_path = "../lambda_function/drift_detect.zip"
}

resource "aws_lambda_function" "agent_lambda" {
  function_name = "bedrock-agent-action-group"
  role          = aws_iam_role.bedrock_agent_role.arn
  handler       = "main.lambda_handler"
  runtime       = "python3.9"
  filename      = data.archive_file.lambda_zip.output_path
  source_code_hash = data.archive_file.lambda_zip.output_base64sha256
  timeout       = 10
}

