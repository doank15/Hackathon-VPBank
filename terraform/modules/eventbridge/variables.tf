variable "lambda_arn" {
  description = "ARN of the Lambda function to invoke"
  type        = string
}

variable "s3_bucket" {
  description = "Name of the S3 bucket containing Terraform state"
  type        = string
}