module "s3" {
  source = "./modules/s3"
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

module "bedrock" {
  source = "./modules/bedrock"
}