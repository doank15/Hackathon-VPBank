module "s3" {
  source = "./modules/s3"
}

module "sns" {
  source = "./modules/sns"
  alert_email = var.alert_email
}

module "aws_config" {
  source = "./modules/aws_config"
  s3_bucket = module.s3.bucket_name
  config_drift_lambda_arn = module.lambda.lambda_arn
}

module "lambda" {
  source = "./modules/lambda"
  sns_topic_arn = module.sns.topic_arn
  s3_bucket = module.s3.bucket_name
  # knowledge_base_id = module.knowledge_base.knowledge_base_id
  # retriever_id = module.knowledge_base.retriever_id
}

module "evenbridge" {
  source = "./modules/eventbridge"
  lambda_arn = module.lambda.lambda_arn
  s3_bucket = module.s3.bucket_name  
}

module "bedrock" {
  source = "./modules/bedrock"
  # drift_lambda_arn = module.lambda.lambda_arn
}

module "knowledge_base" {
  source = "./modules/knowledge_base"
}

resource "aws_lambda_permission" "s3_invoke" {
  statement_id  = "AllowS3Invoke"
  action        = "lambda:InvokeFunction"
  function_name = module.lambda.lambda_arn
  principal     = "s3.amazonaws.com"
  source_arn    = module.s3.bucket_arn
}

resource "aws_s3_bucket_notification" "tfstate_changes" {
  bucket = module.s3.bucket_name
  depends_on = [aws_lambda_permission.s3_invoke]
  lambda_function {
    lambda_function_arn = module.lambda.lambda_arn
    events              = ["s3:ObjectCreated:*"]
    filter_suffix       = ".tfstate"
  }
}