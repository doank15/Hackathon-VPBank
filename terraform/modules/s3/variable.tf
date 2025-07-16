variable "bucket_name" {
    description = "The name of the s3 bucket"
    type = string
}

variable "versioning" {
  description = "Enable versioning for the bucket"
  type = bool
  default = false
}

variable "tags" {
  description = "A map of tags to assign to the bucket"
  type = map(string)
  default = {}
}
