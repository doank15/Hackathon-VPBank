variable "role_arn" {
  type        = string
  description = "IAM role ARN for AWS Config"
}
variable "s3_bucket" {
  type        = string
  description = "S3 bucket for AWS Config logs"
}