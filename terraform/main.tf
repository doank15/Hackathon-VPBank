module "s3" {
  source = "./modules/s3"
  bucket_name = "statetf-bucket-test"
  versioning = true
  tags = {
    Environment = "dev"
    Project = "Hackathon"
  }
}

module "eventbridge" {
  source = "./modules/eventbridge"
  s3_bucket = module.s3.bucket_name
}

module "aws_config" {
  source = "./modules/aws_config"
  s3_bucket = module.s3.bucket_name
}

module "lambda" {
  source = "./modules/lambda"
  s3_bucket = module.s3.bucket_name
}
