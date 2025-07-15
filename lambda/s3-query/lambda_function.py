import boto3
import gzip
import json
import io

s3_client = boto3.client('s3')

def lambda_handler(event, context):
    bucket = event.get("Bucket")
    key = event.get("Key")
    query = event.get("Query")
    input_serialization = event.get("InputSerialization")
    output_serialization = event.get("OutputSerialization")

    if not bucket or not key:
        return {
            "statusCode": 400,
            "body": json.dumps("Bucket and Key are required parameters")
        }

    try:
        if query:
            # Use S3 Select for querying (S3 Select handles decompress transparently)
            response = s3_client.select_object_content(
                Bucket=bucket,
                Key=key,
                ExpressionType='SQL',
                Expression=query,
                InputSerialization=input_serialization or {'JSON': {"Type": "DOCUMENT"}},
                OutputSerialization=output_serialization or {'JSON': {}},
            )

            records = []
            for event in response['Payload']:
                if 'Records' in event:
                    records.append(event['Records']['Payload'].decode('utf-8'))
                elif 'End' in event:
                    break

            result = ''.join(records)
            return {
                "statusCode": 200,
                "body": result
            }

        else:
            # Get entire object
            data = s3_client.get_object(Bucket=bucket, Key=key)
            raw_bytes = data['Body'].read()

            # Check if file is gzipped by signature bytes (magic number: 1f 8b)
            if raw_bytes[:2] == b'\x1f\x8b':
                with gzip.GzipFile(fileobj=io.BytesIO(raw_bytes)) as gz:
                    decompressed_bytes = gz.read()
                contents = decompressed_bytes.decode('utf-8')
            else:
                contents = raw_bytes.decode('utf-8')

            return {
                "statusCode": 200,
                "body": contents
            }

    except Exception as e:
        return {
            "statusCode": 500,
            "body": json.dumps(f"Error getting file from S3: {str(e)}")
        }
