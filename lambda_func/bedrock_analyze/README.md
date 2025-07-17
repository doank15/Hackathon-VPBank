Setup permission:
{
	"Version": "2012-10-17",
	"Statement": [
		{
			"Effect": "Allow",
			"Action": [
				"sns:Publish"
			],
			"Resource": "arn:aws:sns:ap-southeast-1:034362060101:bedrock-drift-analyze"
		},
		{
			"Effect": "Allow",
			"Action": [
				"bedrock:RetrieveAndGenerate",
				"bedrock:Retrieve"
			],
			"Resource": [
				"arn:aws:bedrock:ap-southeast-1:034362060101:knowledge-base/HZDWN3EYQP",
				"arn:aws:bedrock:ap-southeast-1::foundation-model/anthropic.claude-3-5-sonnet-20241022-v2:0",
				"arn:aws:bedrock:ap-southeast-1::foundation-model/anthropic.claude-3-sonnet-20240229-v1:0",
				"arn:aws:bedrock:ap-southeast-1::foundation-model/anthropic.claude-3-haiku-20240307-v1:0"
			]
		},
		{
			"Effect": "Allow",
			"Action": [
				"s3:PutObject"
			],
			"Resource": "arn:aws:s3:::statetf-bucket/drift-logs/*"
		}
	]
}