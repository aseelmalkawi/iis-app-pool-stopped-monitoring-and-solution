#!/bin/bash
region="us-east-1"
instance_id=$1
if [[ "$instance_id" != i-* ]]; then
    # Does not start with "i-"
    echo "Parameter is NOT an AWS instance ID: $instance_id"
    instance_id=$(/usr/local/bin/aws ec2 describe-instances --filters "Name=tag:Name,Values=$Server_name" --query "join(',',Reservations[].Instances[].InstanceId)" --output text)
    echo "Instance ID: $instance_id"
fi
echo "Resetting IIS pools for: $instance_id"

# bash only understands the PowerShell script if it's on one line
sh_command_id=$(/usr/local/bin/aws ssm send-command --document-name "AWS-RunPowerShellScript" --instance-ids "$instance_id" --parameters '{"workingDirectory":[""],"executionTimeout":["3600"],"commands":["Import-Module WebAdministration","$appPools = Get-ChildItem IIS:\\AppPools","foreach ($pool in $appPools) { $state = (Get-WebAppPoolState -Name $pool.Name).Value; if ($state -eq \"Stopped\") { Start-WebAppPool -Name $pool.Name } else { Restart-WebAppPool -Name $pool.Name } }","$websites = Get-Website","foreach ($site in $websites) { Stop-Website -Name $site.Name; Start-Website -Name $site.Name }","Write-Host \"IIS services have been reset.\"","Write-Host \"Web Application Pools:\", ($appPools | ForEach-Object { \"$($_.Name) - $((Get-WebAppPoolState -Name $_.Name).Value)\" })","Write-Host \"Websites:\", ($websites | ForEach-Object { \"$($_.Name) - $($_.State)\" })"]}' --timeout-seconds 600 --region $region --query "Command.CommandId" --output text)

# This command was to test without resetting pools
# sh_command_id=$(/usr/local/bin/aws ssm send-command --document-name "AWS-RunPowerShellScript" --instance-ids "$instance_id" --parameters '{"workingDirectory":[""],"executionTimeout":["3600"],"commands":["Import-Module WebAdministration","$appPools = Get-ChildItem IIS:\\\\AppPools","foreach ($pool in $appPools) { $state = (Get-WebAppPoolState -Name $pool.Name).Value; }","$websites = Get-Website","Write-Host \"IIS services have been reset.\"","Write-Host \"Web Application Pools:\", ($appPools | ForEach-Object { \"$($_.Name) - $((Get-WebAppPoolState -Name $_.Name).Value)\" })","Write-Host \"Websites:\", ($websites | ForEach-Object { \"$($_.Name) - $($_.State)\" })"]}' --timeout-seconds 600 --region "$region" --query "Command.CommandId" --output text)
