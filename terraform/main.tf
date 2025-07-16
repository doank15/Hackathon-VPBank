module "s3" {
  source = "./modules/s3"
  bucket_name = "statetf-bucket-test"
  versioning = true
  tags = {
    Environment = "dev"
    Project = "Hackathon"
  }
}
