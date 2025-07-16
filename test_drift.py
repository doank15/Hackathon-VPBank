#!/usr/bin/env python3
import boto3
import json

def test_drift_detection():
    lambda_client = boto3.client('lambda')
    
    print("Testing drift detection...")
    response = lambda_client.invoke(
        FunctionName='iac-drift-checker',
        Payload=json.dumps({'test': 'manual'})
    )
    
    result = json.loads(response['Payload'].read())
    print("\n=== DRIFT DETECTION RESULTS ===")
    
    if result.get('drift_detected'):
        print("🚨 DRIFT DETECTED!")
        print("\nSummary:")
        print(result.get('summary', 'No summary available'))
        
        if 'details' in result:
            details = result['details']
            print(f"\nDetails:")
            print(f"- Terraform drift: {len(details.get('terraform_managed_drift', []))}")
            print(f"- Unmanaged resources: {len(details.get('unmanaged_resources', []))}")
            print(f"- Deleted managed: {len(details.get('deleted_managed_resources', []))}")
    else:
        print("✅ No drift detected")
    
    print("\nFull Response:")
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    test_drift_detection()