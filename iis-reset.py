#!/usr/bin/env python3
import sys
import boto3
import os

region = "us-east-1"

def get_instance_id(instance_param, server_name=None):
    """
    Convert a server name (tag:Name) into an EC2 instance ID.
    If an instance ID is already provided, just return it.
    """
    if not instance_param.startswith("i-"):
        ec2 = boto3.client("ec2", region_name=region)
        response = ec2.describe_instances(
            Filters=[{"Name": "tag:Name", "Values": [server_name]}]
        )
        instances = [
            i["InstanceId"]
            for r in response["Reservations"]
            for i in r["Instances"]
        ]
        if not instances:
            raise ValueError(f"No EC2 instances found with Name tag '{server_name}'")
        instance_param = ",".join(instances)
    return instance_param
def reset_iis_pools(instance_id):
    """
    Use SSM to run a PowerShell script that:
    - Restarts or starts all IIS app pools safely
    - Restarts all websites safely
    """
    ssm = boto3.client("ssm", region_name=region)
    commands = [r'''
        Import-Module WebAdministration

        $appPools = Get-ChildItem IIS:\AppPools
        foreach ($pool in $appPools) {
            $state = (Get-WebAppPoolState -Name $pool.Name).Value
            if ($state -eq "Stopped") {
                Start-WebAppPool -Name $pool.Name
            } else {
                Restart-WebAppPool -Name $pool.Name
            }
        }

        $websites = Get-Website
        foreach ($site in $websites) {
            Stop-Website -Name $site.Name
            Start-Website -Name $site.Name
        }

        Write-Host "IIS services have been reset."
        Write-Host "Web Application Pools:", (
            $appPools | ForEach-Object {
                "$($_.Name) - $((Get-WebAppPoolState -Name $_.Name).Value)"
            }
        )
        Write-Host "Websites:", (
            $websites | ForEach-Object {
                "$($_.Name) - $($_.State)"
            }
        )
        '''
    ]
    response = ssm.send_command(
        DocumentName="AWS-RunPowerShellScript",
        InstanceIds=[instance_id],
        Parameters={
            "workingDirectory": [""],
            "executionTimeout": ["3600"],
            "commands": commands,
        },
        TimeoutSeconds=600,
    )
    return response["Command"]["CommandId"]
def run(server_input=None):
    """
    Entry point for both imported and direct usage.
    Accepts:
      - instance ID (e.g. 'i-123...')
      - server name (e.g. 'MyServer01')
      - None (falls back to env var Server_name)
    """
    # Jenkins case → env var Server_name
    if not server_input:
        server_input = os.getenv("Server_name")
    if not server_input:
        raise ValueError("No server name or ID provided (argument, function call, or Server_name env variable required).")
    # If it's a server name → resolve to instance ID
    server_name = None if server_input.startswith("i-") else server_input
    instance_id = get_instance_id(server_input, server_name)
    # Execute reset
    command_id = reset_iis_pools(instance_id)
   
if __name__ == "__main__":
    # CLI usage: script.py i-12345  OR  script.py MyServerName
    cli_arg = sys.argv[1] if len(sys.argv) > 1 else None
    run(cli_arg)
