output "lambda_arn" {
  value = aws_lambda_function.drift_checker.arn
}

output "config_drift_arn" {
  value = aws_lambda_function.config_drift.arn
}