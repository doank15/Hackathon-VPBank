resource "aws_s3_bucket" "drift_knowledge_base" {
  bucket = "drift-knowledge-base-${data.aws_caller_identity.current.account_id}"
  
  tags = {
    Name = "Drift Knowledge Base"
    Purpose = "Store drift history for RAG"
  }
}

resource "aws_s3_bucket_versioning" "drift_knowledge_base_versioning" {
  bucket = aws_s3_bucket.drift_knowledge_base.id
  
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "drift_knowledge_base_lifecycle" {
  bucket = aws_s3_bucket.drift_knowledge_base.id

  rule {
    id = "archive-old-reports"
    status = "Enabled"

    transition {
      days = 90
      storage_class = "STANDARD_IA"
    }

    expiration {
      days = 365
    }
  }
}

resource "aws_bedrock_knowledge_base" "drift_kb" {
  name        = "drift-knowledge-base"
  description = "Knowledge base for infrastructure drift history"
  
  storage_configuration {
    type = "S3"
    s3_configuration {
      bucket_name = aws_s3_bucket.drift_knowledge_base.bucket
    }
  }
  
  vector_ingestion_configuration {
    embedding_model_arn = "arn:aws:bedrock:${data.aws_region.current.name}::foundation-model/amazon.titan-embed-text-v1"
    chunking_configuration {
      chunking_strategy = "FIXED_SIZE"
      fixed_size_chunking_configuration {
        max_tokens = 300
        overlap = 30
      }
    }
  }
}

resource "aws_bedrock_retriever" "drift_retriever" {
  name        = "drift-retriever"
  description = "Retriever for infrastructure drift knowledge base"
  knowledge_base_id = aws_bedrock_knowledge_base.drift_kb.id
  
  vector_search_configuration {
    number_of_results = 5
  }
}

data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

output "knowledge_base_id" {
  value = aws_bedrock_knowledge_base.drift_kb.id
}

output "retriever_id" {
  value = aws_bedrock_retriever.drift_retriever.id
}

output "knowledge_base_bucket" {
  value = aws_s3_bucket.drift_knowledge_base.bucket
}