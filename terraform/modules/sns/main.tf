resource "aws_sns_topic" "drift_alerts" {
  name = "iac-drift-alerts"
}

resource "aws_sns_topic_subscription" "email_sub" {
  topic_arn = aws_sns_topic.drift_alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email  # Add this in variables.tf
}

variable "alert_email" {
  description = "Email address to receive drift alerts"
  type        = string
}

output "topic_arn" {
  value = aws_sns_topic.drift_alerts.arn
}