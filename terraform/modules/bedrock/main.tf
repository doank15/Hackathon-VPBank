resource "aws_bedrock_agent" "this" {
  name        = var.agent_name
  description = var.description
  foundation_model_arn = var.foundation_model_arn
  # Thêm các thuộc tính khác nếu cần
}

output "agent_id" {
  value = aws_bedrock_agent.this.id
}