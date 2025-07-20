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
          "s3:ListObjectVersions",
          "s3:GetObjectVersion",
          "s3:GetBucketTagging",
          "s3:PutObject",
          "s3:PutObjectAcl",
          "ec2:DescribeInstances",
          "ec2:DescribeVpcs",
          "lambda:ListFunctions",
          "lambda:InvokeFunction",
          "rds:DescribeDBInstances",
          "rds:ListTagsForResource",
          "dynamodb:ListTables",
          "iam:ListUsers",
          "logs:DescribeLogGroups",
          "ecs:ListClusters",
          "eks:ListClusters",
          "sns:Publish",
          "bedrock:InvokeModel",
          "cloudtrail:LookupEvents",
          "config:GetResourceConfigHistory"
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
  handler          = "drift_checker.lambda_handler"
  runtime          = "python3.10"
  timeout          = 60
  memory_size     = 256
  source_code_hash = filebase64sha256("${path.module}/code/drift_checker.zip")
  environment {
    variables = {
      TFSTATE_BUCKET = var.s3_bucket
      SNS_TOPIC_ARN = var.sns_topic_arn
      BEDROCK_ANALYZER_ARN = aws_lambda_function.bedrock_analyzer.arn
    }
  }
}

resource "aws_lambda_function" "bedrock_analyzer" {
  filename         = "${path.module}/code/bedrock_analyzer.zip"
  function_name    = "bedrock-drift-analyzer"
  role             = aws_iam_role.drift_lambda.arn
  handler          = "bedrock_analyzer.lambda_handler"
  runtime          = "python3.10"
  timeout          = 60
  memory_size      = 512
  source_code_hash = filebase64sha256("${path.module}/code/bedrock_analyzer.zip")
  environment {
    variables = {
      MODEL_ID = "anthropic.claude-3-haiku-20240307-v1:0"
      SNS_TOPIC_ARN = var.sns_topic_arn
      HISTORY_BUCKET = var.s3_bucket
    }
  }
}

resource "aws_lambda_function" "config_history" {
  filename         = "${path.module}/code/config_history.zip"
  function_name    = "config-history-analyzer"
  role             = aws_iam_role.drift_lambda.arn
  handler          = "config_history.lambda_handler"
  runtime          = "python3.10"
  timeout          = 10
  memory_size      = 256
  source_code_hash = filebase64sha256("${path.module}/code/config_history.zip")
  environment {
    variables = {
      SNS_TOPIC_ARN = var.sns_topic_arn
    }
  }
}

resource "aws_iam_role_policy" "bedrock_invoke" {
  name = "bedrock-invoke"
  role = aws_iam_role.drift_lambda.id

  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Effect   = "Allow",
        Action   = ["bedrock:InvokeModel"],
        Resource = "*"  # You can scope this to a specific model ARN
      },
      {
        Effect   = "Allow",
        Action   = [
          "bedrock:Retrieve",
          "bedrock-agent:RetrieveAndGenerate"
        ],
        Resource = "*"
      }
    ]
  })
}

resource "aws_lambda_permission" "allow_drift_to_invoke_bedrock" {
  statement_id  = "AllowDriftToInvokeBedrock"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.bedrock_analyzer.function_name
  principal     = "lambda.amazonaws.com"
  source_arn    = aws_lambda_function.drift_checker.arn
}

resource "aws_lambda_function" "drift_rag" {
  filename         = "${path.module}/code/drift_rag.zip"
  function_name    = "drift-rag-query"
  role             = aws_iam_role.drift_lambda.arn
  handler          = "drift_rag.lambda_handler"
  runtime          = "python3.10"
  timeout          = 60
  memory_size      = 512
  source_code_hash = filebase64sha256("${path.module}/code/drift_rag.zip")
  environment {
    variables = {
      MODEL_ID = "anthropic.claude-3-haiku-20240307-v1:0"
      KNOWLEDGE_BASE_ID = var.knowledge_base_id
      RETRIEVER_ID = var.retriever_id
    }
  }
}