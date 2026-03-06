#  Platform Engineer Assessment

## Repository Structure

```
/assessment-platform-engineer
├── README.md                        ← You are here
├── task1
│   ├── README.md                    ← Deployment & verification guide
│   └── WebServer.yaml               ← CloudFormation template
├── task2
│   ├── README.md                    ← Usage guide
│   └── Manage-EC2Instances.ps1      ← EC2 instance management script
├── task3
│   └── usp_VehiclePart_UpdateDisplayOrder.sql
├── task4
│   ├── README.md                    ← Optimization notes & justifications
│   ├── usp_VehiclePart_ReadSearch.sql
│   └── indexes.sql                  ← Supporting index definitions
└── task5
    ├── README.md                    ← Setup & usage guide
    ├── async_writer.py              ← Async CSV writer implementation
    └── tests
        ├── __init__.py
        └── test_async_writer.py
```

---

## Tasks

### Task 1 — AWS CloudFormation
Deploys a secure, Windows-based web application infrastructure on AWS, including:

- Windows Server EC2 instances with IIS installed via user data
- Auto-recovery on failed EC2 status checks
- Application Load Balancer (ALB) with HTTPS termination
- ACM certificate for TLS
- AWS WAF attached to the ALB
- S3 bucket for application logs with an IAM policy allowing EC2 write access
- Security group permitting HTTPS (443) and RDP (3389)

See `task1/README.md` for deployment steps and verification instructions.

### Task 2 — PowerShell EC2 Management
A PowerShell script that interacts with the infrastructure deployed in Task 1:

- Lists all EC2 instances created by the CloudFormation stack
- Scales the number of running instances up or down

Requires the AWS Tools for PowerShell module. See `task2/README.md` for prerequisites and usage examples.

### Task 3 — T-SQL: Update DisplayOrder
Key behaviours:
- Handles partial updates
- Respects the `UNIQUE (VehicleID, DisplayOrder)` constraint
- Returns integer return codes for all error conditions — no exceptions are raised to the caller

### Task 4 — T-SQL: Optimise ReadSearch
An optimised rewrite of `usp_VehiclePart_ReadSearch`, accompanied by supporting schema changes including primary keys, a foreign key, a non-clustered index, and NOT NULL constraints.

See `task4/README.md` for a full list of changes.

### Task 5 — Python Async CSV Writer
An async Python function that streams an `AsyncIterable` of tuples to multiple CSV files without loading the full dataset into memory, consuming the iterable exactly once.

See `task5/README.md` for installation, usage, and how to run the test suite.

---

## Prerequisites

| Task | Requirements |
|------|-------------|
| Task 1 | AWS CLI configured, IAM permissions for CloudFormation/EC2/S3/ACM/WAF/ELB, an existing VPC/subnets |
| Task 2 | PowerShell 5.1+, AWS Tools for PowerShell (`Install-Module AWSPowerShell.NetCore`) |
| Task 3 & 4 | SQL Server 2016+ (JSON support required for `OPENJSON`) |
| Task 5 | Python 3.8+ (no third-party dependencies) |

---

## Getting Started

Clone the repository and navigate into the relevant task directory. Each task has its own `README.md` with specific setup and run instructions.

```bash
git clone https://github.com//assessment-platform-engineer.git
cd assessment-platform-engineer
```