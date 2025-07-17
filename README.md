# 🔍 Terraform Drift Detection System

This repository implements a **Terraform Drift Detection System** built for the **VPBank Hackathon**, using AWS-native services including Lambda, EventBridge, SNS, S3, CloudTrail, and Amazon Bedrock. The system continuously monitors infrastructure drift and provides intelligent, explainable insights into drift resources between real Infrastructure and the Terraform IAC code.

---

## 🧠 Key Features

- **Automatic Drift Detection**:
  - Triggered on Terraform state file changes in S3.
  - Also supports scheduled drift checks via EventBridge.

- **Change Attribution**:
  - Correlates drift with CloudTrail logs to identify who made the changes.

- **LLM-Powered Explanations**:
  - Uses Amazon Bedrock to generate human-readable explanations of drift and suggested remediation.

- **Alerting**:
  - Sends drift reports via Amazon SNS (email or webhook).
  - Reports include resource diffs, attribution, and action suggestions.

---

## 🛠 Architecture

**Components:**
- **S3** – Stores Terraform state files.
- **EventBridge** – Triggers Lambda on state updates or on schedule.
- **Lambda** – Core drift detection logic:
  - Parses Terraform plan.
  - Compares actual vs. expected infrastructure.
  - Queries CloudTrail for attribution.
  - Calls Amazon Bedrock for explanation generation.
- **CloudTrail** – Audits user actions for attribution.
- **SNS** – Sends alert notifications.

![Architecture Diagram](./architecture.png)

---

## 🚀 Getting Started

### Prerequisites

- AWS CLI configured
- Terraform ≥ 5.0
- An AWS account with permissions to create:
  - Lambda, S3, CloudTrail, SNS, IAM, EventBridge

### 1. Clone and Deploy

```bash
git clone https://github.com/doank15/Hackathon-VPBank.git
cd Hackathon-VPBank/terraform

terraform init
terraform apply
```

### 2. Upload State File

Place your Terraform state in the configured S3 bucket:

```bash
aws s3 cp terraform.tfstate s3://your-drift-bucket/envs/prod/terraform.tfstate
```

This triggers the drift detection Lambda.

---

## 📬 Sample Alert

```
Drift Detected: 2 resources changed outside Terraform.

- aws_security_group.sg_web (MODIFIED)
- aws_s3_bucket.logs (DELETED)

Change Attributed To: user:alice@vpbank.com
Explanation (via Bedrock):
"The security group was updated manually to allow wider IP access. This could pose a security risk."

Recommended Action:
- Revert the changes via Terraform apply
- OR import and manage manually updated resources
```

---

## 🤖 How It Works

1. **Trigger**: On new state file upload (S3 event), Lambda is invoked.
2. **Plan Comparison**: Terraform is run in `-refresh-only` mode to detect drift.
3. **Attribution**: CloudTrail is queried for changes to impacted resources.
4. **Explanation**: Amazon Bedrock (Claude or Jurassic-2) generates natural language summaries.
5. **Notification**: SNS delivers a report to subscribers.

---

## 🧪 Testing Locally

You can simulate drift detection locally with:

```bash
cd scripts/
./simulate-drift.sh --state-file ./examples/prod.tfstate
```

---

## 📌 Roadmap

- [x] S3-triggered detection
- [x] Scheduled drift check via EventBridge
- [x] CloudTrail-based attribution
- [x] LLM summaries with Bedrock
- [ ] Web dashboard for drift history
- [ ] Auto-remediation via approval flow

---

## 📜 License

MIT License — see [LICENSE](./LICENSE)

---