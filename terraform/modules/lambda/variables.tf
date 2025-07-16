variable "function_name" {
  type        = string
  description = "Lambda function name"
}
variable "role_arn" {
  type        = string
  description = "IAM role ARN for Lambda"
}
variable "handler" {
  type        = string
  description = "Lambda handler"
}
variable "runtime" {
  type        = string
  description = "Lambda runtime"
}
variable "filename" {
  type        = string
  description = "Path to deployment package"
}
variable "environment_variables" {
  type        = map(string)
  default     = {}
  description = "Environment variables"
}
variable "s3_bucket" {
  type        = string
  description = "S3 bucket for logs or code"
}