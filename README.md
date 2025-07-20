# Infrastructure Drift Detection System

A comprehensive system for detecting and reporting infrastructure drift in AWS environments.

## Overview

This project provides real-time detection of infrastructure drift - when your actual AWS resources differ from what's defined in your Terraform code. It helps maintain infrastructure as code integrity by alerting you when resources are:

- Created outside of Terraform
- Modified outside of Terraform
- Deleted from AWS while still in Terraform code

## Features

- **Multi-source drift detection**:
  - Terraform state vs. actual AWS resources
  - AWS Config configuration changes
  - CloudTrail API call monitoring
  - S3 state file change detection

- **Comprehensive resource coverage**:
  - EC2 instances
  - S3 buckets
  - IAM users
  - RDS databases
  - VPCs and subnets
  - Lambda functions
  - DynamoDB tables

- **User attribution**:
  - Identifies who made changes
  - Shows when changes were made
  - Indicates which region changes occurred in

- **Multiple detection methods**:
  - Scheduled scans (every 5 minutes)
  - Real-time event-based detection
  - Manual invocation

- **Detailed reporting**:
  - Email notifications via SNS
  - Comprehensive drift summaries
  - Change categorization

## Architecture

![Architecture Diagram](docs/architecture.png)

The system consists of:

1. **Lambda Functions**:
   - `iac-drift-checker`: Main drift detection function
   - `iac-config-listener`: Processes AWS Config events

2. **EventBridge Rules**:
   - Scheduled drift checks (every 5 minutes)
   - AWS Config change detection
   - CloudTrail API call monitoring
   - S3 state file change detection

3. **AWS Config**:
   - Configuration recorder
   - Delivery channel

4. **SNS Topic**:
   - Email notifications

## Setup

### Prerequisites

- AWS CLI configured
- Terraform v1.0+
- S3 bucket for Terraform state

### Deployment

1. Clone the repository:

   ```
   git clone https://github.com/yourusername/infrastructure-drift-detection.git
   cd infrastructure-drift-detection
   ```

2. Update variables:

   ```
   cp terraform.tfvars.example terraform.tfvars
   # Edit terraform.tfvars with your values
   ```

3. Deploy:

   ```
   terraform init
   terraform apply -var="alert_email=your-email@example.com"
   ```

## Usage

### Viewing Drift Reports

Drift reports are sent to the email address specified during deployment. Each report includes:

- **Unmanaged Resources**: Resources created outside of Terraform
- **Modified Resources**: Terraform-managed resources changed outside of Terraform
- **Deleted Resources**: Resources deleted from AWS but still in Terraform code

### Manual Drift Detection

To run drift detection manually:

```bash
aws lambda invoke --function-name iac-drift-checker --payload '{}' response.json
cat response.json
```

## Customization

### Adding Resource Types

Edit `simple_drift_checker.py` to add support for additional resource types:

1. Add resource discovery in `get_actual_resources()`
2. Add comparison logic in `run_full_drift_detection()`
3. Add CloudTrail event names in `get_change_author()`

### Modifying Detection Frequency

Change the schedule expression in `modules/eventbridge/main.tf`:

```hcl
schedule_expression = "rate(5 minutes)"  # Change to desired frequency
```

## Troubleshooting

- **Missing CloudTrail Events**: Extend the search period in `get_change_author()` by increasing `timedelta(days=30)` to a larger value
- **Lambda Timeouts**: Optimize resource discovery or increase Lambda timeout in `modules/lambda/drift_checker.tf`
- **False Positives**: Add exclusion patterns in `run_full_drift_detection()`

## License

MIT

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
