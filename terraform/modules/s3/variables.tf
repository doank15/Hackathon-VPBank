variable "bucket_name" {
  description = "The name of the S3 bucket"
  type        = string
}

variable "versioning" {
  description = "Enable versioning"
  type        = bool
  default     = false
}

variable "tags" {
  description = "Tags for the bucket"
  type        = map(string)
  default     = {}
} 