terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 4.16"
    }
  }
  backend "s3" {
    bucket = "statetf-bucket-test"
    region = "ap-southeast-1"
    key = "terraform.tfstate"
  }
}

provider "aws" {
  region = var.region
}