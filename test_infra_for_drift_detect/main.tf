terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 4.1"
    }
  }
  backend "s3" {
    bucket = "statetf-bucket"
    region = "ap-southeast-1"
    key = "terraform.tfstate"
  }
}

provider "aws" {
  region  = "ap-southeast-1"
}

resource "aws_vpc" "main" {
  cidr_block = "10.0.0.0/16"
  enable_dns_hostnames = true
  tags = {
    Name = "main-vpc"
  }
}

resource "aws_subnet" "private_subnet" {
  vpc_id                  = aws_vpc.main.id
  cidr_block              = "10.0.1.0/24"
  map_public_ip_on_launch = false
  tags = {
    Name = "private-subnet"
  }
}

resource "aws_instance" "ec2_instance" {
  ami           = "ami-0435fcf800fb5418d"
  instance_type = "t2.micro"
  subnet_id = aws_subnet.private_subnet.id
  associate_public_ip_address = false

  tags = {
    owner = "dda"
    environment = "prod"
  }
}