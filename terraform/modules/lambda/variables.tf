variable "s3_bucket" {
  description = "Name of the S3 bucket for Terraform state"
  type        = string
}

variable "sns_topic_arn" {
  description = "ARN of the SNS topic for drift alerts"
  type        = string
}

variable "knowledge_base_id" {
  description = "ID of the Bedrock knowledge base for drift history"
  type        = string
  default     = ""
}

variable "retriever_id" {
  description = "ID of the Bedrock retriever for the knowledge base"
  type        = string
  default     = ""
}