# Task 2 — PowerShell: EC2 Instance Management

## Prerequisites

- PowerShell 5.1+ or PowerShell 7+
- AWS Tools for PowerShell installed:
  ```powershell
  Install-Module -Name AWSPowerShell.NetCore -Scope CurrentUser -Force
  ```
- AWS credentials configured, either via:
  - `aws configure` (shared credentials file), or
  - Environment variables (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_DEFAULT_REGION`), or
  - An IAM instance profile if running from an EC2 instance
- IAM permissions required:
  - `ec2:DescribeInstances`
  - `cloudformation:DescribeStackResource`
  - `autoscaling:DescribeAutoScalingGroups`
  - `autoscaling:UpdateAutoScalingGroup`
- The CloudFormation stack from Task 1 must already be deployed

---

## Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `StackName` | Yes | — | Name of the CloudFormation stack to target |
| `Action` | No | `None` | `Increase`, `Decrease`, or `None` |
| `CapacityAdjustmentStep` | No | `1` | Number of instances to add or remove per run |

---

## Usage

### List all EC2 instances in the stack

```powershell
.\Manage-EC2Instances.ps1 -StackName "my-web-server"
```

Output:
```
Listing EC2 instances in stack: my-web-server
Found 2 instances my-web-server:

InstanceId          State    InstanceType PublicIpAddress
----------          -----    ------------ ---------------
i-0abc123456def789  running  t3.micro     52.10.20.30
i-0xyz987654fed321  running  t3.micro     52.10.20.31
```

---

### Increase the number of running instances by 1

```powershell
.\Manage-EC2Instances.ps1 -StackName "my-web-server" -Action Increase
```

### Increase by a custom step

```powershell
.\Manage-EC2Instances.ps1 -StackName "my-web-server" -Action Increase -CapacityAdjustmentStep 2
```

### Decrease the number of running instances by 1

```powershell
.\Manage-EC2Instances.ps1 -StackName "my-web-server" -Action Decrease
```

> The script always clamps the new capacity within the ASG's configured `MinSize` and `MaxSize` (1–3 as defined in the CloudFormation template). Requesting a scale beyond those bounds will silently stop at the limit rather than error.

---

## Notes

- The listing and scaling operations run independently. Even if the stack has no instances to list, the scaling action will still execute, and vice versa.
- The script targets the `WebServerASG` Auto Scaling Group by logical resource ID. If the CloudFormation stack was deployed with a different template that uses a different logical ID, line 38 in the script will need to be updated accordingly.
- Scaling changes are eventually consistent — after running with `Increase` or `Decrease`, allow 1–2 minutes for the ASG to launch or terminate instances before re-running the listing to see the updated state.