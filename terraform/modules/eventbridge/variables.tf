variable "name" {
  type        = string
  description = "EventBridge bus name"
}
variable "s3_bucket" {
  type        = string
  description = "S3 bucket for event logs"
}