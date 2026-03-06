# Task 1 — CloudFormation: Windows Web Server

## Prerequisites

- AWS CLI installed and configured (`aws configure`)
- IAM permissions for: CloudFormation, EC2, S3, IAM, ACM, ELB, WAFv2, AutoScaling
- A domain name you control, for DNS validation of the ACM certificate

---

## Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `DomainName` | No | `*.example.com` | Domain for the ACM certificate |
| `VpcId` | Yes | — | ID of the VPC to deploy into |
| `Subnets` | Yes | — | Comma-separated list of at least two subnet IDs |
| `DesiredCapacity` | No | `1` | Number of EC2 instances to run (1–3) |
| `WindowsImageId` | No | Windows Server 2022 (SSM) | SSM parameter path for the AMI |

---

## Deployment

**1. Clone or download `WebServer.yaml` into your working directory.**

**2. Deploy the stack:**

```bash
aws cloudformation deploy \
  --template-file WebServer.yaml \
  --stack-name my-web-server \
  --parameter-overrides \
      DomainName="myapp.example.com" \
      VpcId="vpc-0abc123456" \
      Subnets="subnet-0aaa111,subnet-0bbb222" \
      DesiredCapacity=1 \
  --capabilities CAPABILITY_IAM \
  --region us-east-1
```

> `--capabilities CAPABILITY_IAM` is required because the template creates an IAM role and instance profile.

**3. Validate the ACM certificate.**

The certificate starts in `PENDING_VALIDATION` and the stack will wait until it is issued. After the stack begins creating, retrieve the required CNAME record:

```bash
aws acm describe-certificate \
  --certificate-arn $(aws cloudformation describe-stack-resource \
    --stack-name my-web-server \
    --logical-resource-id SiteCertificate \
    --query 'StackResourceDetail.PhysicalResourceId' \
    --output text) \
  --query 'Certificate.DomainValidationOptions[*].ResourceRecord'
```

Add the returned CNAME record to your DNS provider. The certificate will validate automatically and the stack will continue deploying.

**4. Retrieve the stack outputs once deployment completes:**

```bash
aws cloudformation describe-stacks \
  --stack-name my-web-server \
  --query 'Stacks[0].Outputs'
```

This returns the ALB DNS name, ALB ARN, and the S3 log bucket name.

---

## Verifying the Setup

### EC2 Instances

Confirm the Auto Scaling Group launched the expected number of instances:

```bash
aws autoscaling describe-auto-scaling-groups \
  --auto-scaling-group-names $(aws cloudformation describe-stack-resource \
    --stack-name my-web-server \
    --logical-resource-id WebServerASG \
    --query 'StackResourceDetail.PhysicalResourceId' \
    --output text) \
  --query 'AutoScalingGroups[0].{Desired:DesiredCapacity,Min:MinSize,Max:MaxSize,Instances:Instances[*].{Id:InstanceId,State:LifecycleState,Health:HealthStatus}}'
```

### IIS

Confirm IIS is responding through the ALB. Use the `LoadBalancerDNS` output value:

```bash
curl -k https://<LoadBalancerDNS>
```

You should receive the default IIS welcome page HTML. The `-k` flag bypasses certificate validation if you haven't pointed your domain's DNS A record at the ALB yet.

### ALB Target Health

Confirm the EC2 instances are healthy in the target group:

```bash
aws elbv2 describe-target-health \
  --target-group-arn $(aws cloudformation describe-stack-resource \
    --stack-name my-web-server \
    --logical-resource-id LBTargetGroup \
    --query 'StackResourceDetail.PhysicalResourceId' \
    --output text)
```

All instances should show `"State": "healthy"`. If they show `"State": "unhealthy"`, IIS may still be initialising — wait 2–3 minutes and retry.

### WAF

Confirm the WebACL is associated with the ALB:

```bash
aws wafv2 list-resources-for-web-acl \
  --web-acl-arn $(aws cloudformation describe-stack-resource \
    --stack-name my-web-server \
    --logical-resource-id WebACL \
    --query 'StackResourceDetail.PhysicalResourceId' \
    --output text) \
  --region us-east-1
```

The ALB ARN should appear in the response.

### S3 Logs

After the ALB receives traffic, access logs are delivered to the S3 bucket under the `alb/` prefix. Allow 5–10 minutes after first traffic, then check:

```bash
aws s3 ls s3://$(aws cloudformation describe-stacks \
  --stack-name my-web-server \
  --query 'Stacks[0].Outputs[?OutputKey==`LogsBucketName`].OutputValue' \
  --output text)/alb/
```

---

## Teardown

```bash
aws cloudformation delete-stack --stack-name my-web-server
```

> The S3 bucket must be emptied before the stack can delete successfully. Either empty it manually in the console first, or run:
> ```bash
> aws s3 rm s3://<LogsBucketName> --recursive
> ```

---

## Production Concerns & Recommendations

The following items are outside the mandatory scope but should be addressed before this template is used in production.

**Security**
- RDP (port 3389) should be further restricted to a specific bastion host IP or VPN CIDR rather than the broad `10.0.0.0/8` range.
- Consider replacing direct RDP access with AWS Systems Manager Session Manager, which eliminates the need to open port 3389 entirely.
- `t3.micro` is suitable for testing only. Right-size the instance type based on expected load before going to production.
- The ACM certificate's `DomainName` defaults to `*.example.com`. This must be updated to a real domain before deployment.
- IMDSv1 is disabled (`HttpEndpoint: disabled`), which is correct. If any application code requires instance metadata, switch to IMDSv2 (`HttpEndpoint: enabled`, `HttpTokens: required`) rather than re-enabling v1.

**Reliability**
- The `HealthCheckGracePeriod` is set to 300 seconds. If IIS takes longer to start (e.g. on first boot when `Install-WindowsFeature` runs), instances may be terminated prematurely. Monitor actual startup times and increase this value if needed.
- Consider adding an S3 lifecycle policy to expire or transition old log files to cut storage costs over time.

**Observability**
- No CloudWatch alarms are defined. At minimum, add alarms for ALB 5xx error rate, target response time, and ASG instance health.
- Consider enabling VPC Flow Logs for network-level visibility.

**CI/CD**
- The template should be linted with `cfn-lint` and validated with `aws cloudformation validate-template` as part of any deployment pipeline before being applied to production.