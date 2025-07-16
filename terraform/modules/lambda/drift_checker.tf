resource "aws_iam_role" "drift_lambda" {
  name = "drift-checker-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17",
    Statement = [{
      Effect = "Allow",
      Principal = { Service = "lambda.amazonaws.com" },
      Action = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "drift_lambda_basic" {
  role       = aws_iam_role.drift_lambda.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy" "drift_lambda_permissions" {
  name = "drift-lambda-permissions"
  role = aws_iam_role.drift_lambda.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:ListBuckets",
          "ec2:DescribeInstances",
          "ec2:DescribeVpcs",
          "lambda:ListFunctions",
          "rds:DescribeDBInstances",
          "dynamodb:ListTables",
          "iam:ListUsers",
          "logs:DescribeLogGroups",
          "ecs:ListClusters",
          "eks:ListClusters",
          "sns:Publish",
          "bedrock:InvokeModel",
          "cloudtrail:LookupEvents"
        ]
        Resource = "*"
      }
    ]
  })
}

resource "aws_lambda_function" "drift_checker" {
  filename         = "${path.module}/code/drift_checker.zip"
  function_name    = "iac-drift-checker"
  role             = aws_iam_role.drift_lambda.arn
  handler          = "lambda_function_drift_checker.lambda_handler"
  runtime          = "python3.10"
  timeout          = 60
  source_code_hash = filebase64sha256("${path.module}/code/drift_checker.zip")
  environment {
    variables = {
      TFSTATE_BUCKET = var.s3_bucket
      SNS_TOPIC_ARN = var.sns_topic_arn
    }
  }
}

resource "aws_iam_role_policy" "bedrock_invoke" {
  name = "bedrock-invoke"
  role = aws_iam_role.drift_lambda.id

  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [{
      Effect   = "Allow",
      Action   = ["bedrock:InvokeModel"],
      Resource = "*"  # You can scope this to a specific model ARN
    }]
  })
}

