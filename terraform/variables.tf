variable "region" {
  type = string
  default = "ap-southeast-1"
}

variable "alert_email" {
  type = string
  description = "Email address to receive alerts"
}