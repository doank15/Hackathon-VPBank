variable "lambda_arn" {}
variable "s3_bucket" {}

resource "aws_cloudwatch_event_rule" "cron_rule" {
  name = "iac-drift-check-cron"
  schedule_expression = "rate(1 hour)"
}

resource "aws_cloudwatch_event_target" "cron_target" {
  rule = aws_cloudwatch_event_rule.cron_rule.name
  arn  = var.lambda_arn
}

resource "aws_lambda_permission" "allow_cron" {
  statement_id  = "AllowExecutionFromCron"
  action        = "lambda:InvokeFunction"
  function_name = var.lambda_arn
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.cron_rule.arn
}
