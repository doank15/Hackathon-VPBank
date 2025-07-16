variable "agent_name" {
  type        = string
  description = "Tên của Bedrock Agent"
}
variable "description" {
  type        = string
  description = "Mô tả agent"
  default     = ""
}
variable "foundation_model_arn" {
  type        = string
  description = "ARN của Bedrock Foundation Model"
}
