Param(
    [Parameter(Mandatory=$true)]
    [string]$StackName,

    [Parameter(Mandatory=$false)]
    # Im using none here instead of $null, because i cant use $null as a valid value
    [ValidateSet("Increase", "Decrease", "None")]
    [string]$Action = "None",

    [Parameter(Mandatory=$false)]
    [int]$CapacityAdjustmentStep = 1
)

Write-Host "Listing EC2 instances in stack: $StackName"

try {    
    ### List all EC2 instances ###
    # Filter instances by stack-name ($StackName)
    $instances = (Get-EC2Instance -Filter @( @{ Name = 'tag:aws:cloudformation:stack-name'; Values = @($StackName) })).Instances

    # Check if any instances were found
    if ($null -eq $instances) {
        Write-Host "No EC2 instances found for stack $($StackName)."
    }
    else {
        Write-Host "Found $($instances.Count) instances $($StackName):"
        
        $instances | Select-Object InstanceId, @{Name="State";Expression={$_.State.Name}}, InstanceType, PublicIpAddress | Format-Table
    }
} catch {
    Write-Error "Error listing EC2 instances: $($_.Exception.Message)"
}

try {    
    ### Scaling EC2 instances ###
    # Is there an Action that needs to be fufilled?
    if ($Action -ne "None") {
        $logicalResourceId = "WebServerASG"
        $stackResource = Get-CFNStackResource -StackName $StackName -LogicalResourceId $logicalResourceId
        $asgName = $stackResource.PhysicalResourceId
        $asg = Get-ASAutoScalingGroup -AutoScalingGroupName $asgName

        if ($null -eq $asg) {
            throw "Could not find an Auto Scaling Group for stack: $($StackName)"
        }
        else {
            $currentCapacity = $asg.DesiredCapacity
            $minSize = $asg.MinSize
            $maxSize = $asg.MaxSize

            if ($Action -eq "Increase") {
                $newCapacity = [Math]::Min($maxSize, $currentCapacity + $CapacityAdjustmentStep)
            } else {
                $newCapacity = [Math]::Max($minSize, $currentCapacity - $CapacityAdjustmentStep)
            }    
            
            Write-Host "Updating ASG $($asgName): $($currentCapacity) to $($newCapacity)"
            
            Update-ASAutoScalingGroup -AutoScalingGroupName $asgName -DesiredCapacity $newCapacity -MinSize $minSize -MaxSize $maxSize | Out-Null

            Write-Host "Successfully updated capacity for $($asgName) to $($newCapacity)."
        }
    }
} catch {
    Write-Error "Error Scaling instances: $($_.Exception.Message)"
}    
