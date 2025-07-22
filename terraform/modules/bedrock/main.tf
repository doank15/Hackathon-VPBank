variable "drift_lambda_arn" {
  description = "ARN of the drift detection Lambda function"
  type        = string
}

resource "aws_iam_role" "bedrock_role" {
  name = "BedrockServiceRole"
  assume_role_policy = jsonencode({
    Version = "2012-10-17",
    Statement = [{
      Action = "sts:AssumeRole",
      Principal = { Service = "bedrock.amazonaws.com" },
      Effect = "Allow"
    }]
  })
}

resource "aws_iam_role_policy" "bedrock_lambda_access" {
  name = "BedrockLambdaAccessPolicy"
  role = aws_iam_role.bedrock_role.id
  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Effect = "Allow",
        Action = [
          "lambda:InvokeFunction"
        ],
        Resource = var.drift_lambda_arn
      }
    ]
  })
}

# resource "aws_bedrock_agent" "drift_detection_agent" {
#   name        = "DriftDetectionAgent"
#   role_arn    = aws_iam_role.bedrock_role.arn
#   description = "Agent for detecting drift in AWS resources"

#   agent_configuration {
#     type = "LAMBDA"
#     lambda_function_arn = var.drift_lambda_arn
#   }

#   tags = {
#     Environment = "Production"
#     Purpose     = "Drift Detection"
#   }
# }
# resource "aws_bedrock_agent_version" "drift_detection_agent_v1" {
#   agent_id = aws_bedrock_agent.drift_detection_agent.id
#   version  = "1"

#   agent_configuration {
#     type = "LAMBDA"
#     lambda_function_arn = var.drift_lambda_arn
#   }

#   tags = {
#     Environment = "Production"
#     Purpose     = "Drift Detection"
#   }
# }
# resource "aws_bedrock_agent_alias" "drift_detection_agent_alias" {
#   agent_id     = aws_bedrock_agent.drift_detection_agent.id
#   alias_name   = "v1"
#   description  = "Alias for the drift detection agent version 1"
#   agent_version = aws_bedrock_agent_version.drift_detection_agent_v1.version

#   tags = {
#     Environment = "Production"
#     Purpose     = "Drift Detection"
#   }
# }