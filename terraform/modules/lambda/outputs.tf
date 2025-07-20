output "lambda_arn" {
  value = aws_lambda_function.drift_checker.arn
}

output "config_drift_arn" {
  value = aws_lambda_function.drift_checker.arn
}

output "bedrock_analyzer_arn" {
  value = aws_lambda_function.bedrock_analyzer.arn
}

output "config_history_arn" {
  value = aws_lambda_function.config_history.arn
}
