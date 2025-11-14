# IIS Application Pool Monitoring & Auto-Reset

This repository contains a New Relic Flex integration for monitoring IIS application pools, along with automated remediation scripts to reset pools when issues are detected.

## Overview

The solution consists of three main components:

1. **New Relic Flex Integration** - Monitors IIS app pool status
2. **Automated Reset Scripts** - Python and Bash scripts to restart app pools via AWS SSM
3. **GitHub Actions Workflow** - Manual trigger for IIS resets

## Components

### 1. New Relic Flex Integration

**File:** `nri-flex-app-pools.yml`

Monitors all IIS application pools and websites on Windows servers, reporting their status to New Relic.

```yaml
integrations:
  - name: nri-flex
    config:
      name: iisAppPools
      apis:
        - event_type: appPoolCheck
          shell: powershell
          commands:
            - run: |
                Get-Website | ForEach-Object {
                  $appPool = $_.applicationPool
                  $state = (Get-WebAppPoolState -Name $appPool).Value
                  $status = if ($state -eq "Started") { 1 } else { 0 }
                  [PSCustomObject]@{
                    appPoolName   = $appPool
                    appPoolStatus = $status
                  }
                } | ConvertTo-Json
```

**Deployment:**
- Place this configuration in the New Relic infrastructure agent's `integrations.d` directory
- Default location: `C:\Program Files\New Relic\newrelic-infra\integrations.d\`
- Restart the New Relic infrastructure service after deployment

**Metrics Collected:**
- `appPoolName` - Name of the application pool
- `appPoolStatus` - Status (1 = Started, 0 = Stopped)
- Event type: `appPoolCheck`

**NRQL Query Example:**
```sql
SELECT latest(appPoolStatus) 
FROM appPoolCheck
-- if you want to filter for a specific pool:
WHERE appPoolName = 'The pool'
FACET tags.Hostname aws.arn
```
Window duration and thresholds can be set as needed.

**Suggested Alert Conditions:**
- **Critical:** Any app pool stopped for more than 2 minutes

### 2. IIS Reset Scripts

#### Python Script (Recommended)

**File:** `iis-reset.py`

```bash
# Usage with instance ID
python iis_reset.py i-1234567890abcdef0

# Usage with server name (tag:Name)
python iis_reset.py MyServerName

# Usage with environment variable
export Server_name=MyServerName
python iis_reset.py
```

**Features:**
- Accepts EC2 instance ID or server name (resolved via tag:Name)
- Restarts all IIS application pools safely
- Restarts all websites
- Uses AWS Systems Manager (SSM) for remote execution
- Supports both CLI and programmatic usage

**Dependencies:**
- `boto3` - AWS SDK for Python
- AWS credentials configured, or the runner server has the necessary IAM roles
- Target EC2 instance must have the SSM agent installed

#### Bash Script (Alternative)

**File:** `iis-reset.sh`

```bash
# Usage with instance ID
./iis_reset.sh i-1234567890abcdef0

# Usage with server name
export Server_name=MyServerName
./iis_reset.sh MyServerName
```

**Features:**
- Lightweight bash implementation
- Same functionality as the Python version
- Uses AWS CLI

### 3. GitHub Actions Workflow

**File:** `iis-actions-wf.yml`

Manual workflow trigger for resetting IIS on demand.

```yaml
name: Reset_IIS
on:
  workflow_dispatch:
    inputs:
      server_name:
        description: 'Name of the server to reset IIS on'
        required: true
        type: string
```

**Usage:**
1. Pleace the file in the default actions directory: .github/workflows
2. Navigate to the Actions tab in GitHub
3. Select "iis-reset" workflow
4. Click "Run workflow"
5. Enter the server name
6. Click the "Run workflow" button

## Setup Instructions

### Prerequisites

- **AWS Account or server** with appropriate permissions:
  - EC2: `describe-instances`
  - SSM: `send-command`, `get-command-invocation`
    
- **The affected EC2 Instances** with:
  - Windows Server with IIS installed
  - AWS SSM Agent installed and running
  - Appropriate IAM role for SSM (e.g., `AmazonSSMManagedInstanceCore`)
    
- **New Relic Infrastructure Agent** installed on target servers

### Installation

1. **Deploy New Relic Flex Integration:**
   ```powershell
   # Start PowerShell as admin from the location of the integration to copy the YAML configuration to the integrations directory
   Copy-Item newrelic-flex-iis.yml "C:\Program Files\New Relic\newrelic-infra\integrations.d\"
   
   # Restart New Relic service
   Restart-Service newrelic-infra
   ```

3. **Configure GitHub Actions (if needed):**
   - Ensure AWS credentials are set up as repository secrets:
     - `AWS_ACCESS_KEY_ID`
     - `AWS_SECRET_ACCESS_KEY`
     - `AWS_REGION` (default: us-east-1)

## How It Works

### Monitoring Flow

1. New Relic Flex runs PowerShell commands at regular intervals
2. Queries all websites and their associated app pools
3. Checks the state of each app pool
4. Converts state to binary status (1=Started, 0=Stopped)
5. Reports data to New Relic as custom events

### Remediation Flow

1. Script receives server name or instance ID
2. If server name provided, queries EC2 for matching instance
3. Sends PowerShell commands via SSM to target instance
4. PowerShell script on target:
   - Imports WebAdministration module
   - Iterates through all app pools
   - Starts stopped pools, restarts running pools
   - Stops and starts all websites
   - Reports final status
5. Script waits for command completion
6. Returns success or failure status

## Automated Remediation

To automatically reset IIS when issues are detected:

1. Set up the New Relic alert condition
2. Configure webhook destination pointing to GitHub Actions API
3. Trigger the `Reset_IIS` workflow automatically
4. Alternative: Use Slack or PagerDuty notifications.

## Troubleshooting

### Common Issues

**SSM Command Fails:**
- Verify SSM agent is running on the target instance
- Check IAM role has SSM permissions
- Ensure security groups allow SSM traffic

**Server Name Not Found:**
- Verify EC2 instance has the correct `Name` tag
- Check AWS credentials and region configuration
- Ensure EC2 permissions are granted

**New Relic Not Receiving Data:**
- Verify New Relic infrastructure agent is running
- Check YAML syntax in the integration file
- Review agent logs: `C:\Program Files\New Relic\newrelic-infra\newrelic-infra.log`

**App Pool Won't Start:**
- Check Windows Event Viewer for IIS errors
- Verify app pool identity has correct permissions
- Review application-specific logs

### Debugging

**Enable verbose logging in Python script:**
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

**Test SSM connectivity:**
```bash
aws ssm describe-instance-information \
  --filters "Key=tag:Name,Values=YourServerName"
```

**Test PowerShell commands locally:**
```powershell
Import-Module WebAdministration
Get-ChildItem IIS:\AppPools
Get-Website
```

## Security Considerations

- **Least Privilege:** Grant minimum required AWS permissions
- **Credentials:** Never commit AWS credentials to repository
- **SSM Access:** Limit SSM access to authorised users/roles
- **Audit Logging:** Enable CloudTrail for SSM command tracking
- **Network Security:** Ensure proper VPC and security group configuration

## Support

For issues or questions:
- Open an issue in this repository
- Contact your DevOps team
- Review AWS SSM documentation: https://docs.aws.amazon.com/systems-manager/
