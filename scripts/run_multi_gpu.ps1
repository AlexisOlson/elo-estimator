# Helper script to launch multiple GPU workers for distributed PGN analysis
#
# Usage: .\scripts\run_multi_gpu.ps1 <pgn_file> <output_file> <num_gpus> [additional_args...]
#
# Example:
#   .\scripts\run_multi_gpu.ps1 games.pgn output.json 4 --search.nodes=1000

param(
    [Parameter(Mandatory=$true, Position=0)]
    [string]$PgnFile,

    [Parameter(Mandatory=$true, Position=1)]
    [string]$OutputFile,

    [Parameter(Mandatory=$true, Position=2)]
    [int]$NumGpus,

    [Parameter(ValueFromRemainingArguments=$true)]
    [string[]]$ExtraArgs
)

# Derive work directory from output file
$WorkDir = $OutputFile -replace '\.json$', '_work'

Write-Host "Starting distributed PGN analysis:" -ForegroundColor Cyan
Write-Host "  PGN file: $PgnFile"
Write-Host "  Output file: $OutputFile"
Write-Host "  Work directory: $WorkDir"
Write-Host "  Number of GPUs: $NumGpus"
Write-Host "  Extra args: $($ExtraArgs -join ' ')"
Write-Host ""

# Create work directory
New-Item -ItemType Directory -Force -Path $WorkDir | Out-Null

# Launch workers as background jobs
$Jobs = @()
for ($gpu = 0; $gpu -lt $NumGpus; $gpu++) {
    $WorkerId = "GPU$gpu"
    $LogFile = Join-Path $WorkDir "$WorkerId.log"

    Write-Host "Launching worker $WorkerId (logging to $LogFile)..." -ForegroundColor Green

    $JobName = "Worker_$WorkerId"
    $ScriptBlock = {
        param($PgnFile, $OutputFile, $WorkDir, $WorkerId, $Gpu, $ExtraArgs)

        $Args = @(
            "scripts/analyze_pgn.py",
            $PgnFile,
            $OutputFile,
            "--work-dir=$WorkDir",
            "--worker-id=$WorkerId",
            "--lc0.backend-opts=gpu=$Gpu"
        ) + $ExtraArgs

        python @Args
    }

    $Job = Start-Job -Name $JobName -ScriptBlock $ScriptBlock `
        -ArgumentList $PgnFile, $OutputFile, $WorkDir, $WorkerId, $gpu, $ExtraArgs

    $Jobs += $Job
    Write-Host "  Started job: $($Job.Name) (ID: $($Job.Id))" -ForegroundColor Gray
}

Write-Host ""
Write-Host "All workers launched. Waiting for completion..." -ForegroundColor Cyan
Write-Host "Monitor progress with: Get-Job | Receive-Job -Keep"
Write-Host ""

# Wait for all jobs and display their output
$Jobs | ForEach-Object {
    Write-Host "Waiting for $($_.Name)..." -ForegroundColor Yellow
    $_ | Wait-Job | Out-Null

    # Save output to log file
    $WorkerId = $_.Name -replace 'Worker_', ''
    $LogFile = Join-Path $WorkDir "$WorkerId.log"
    $_ | Receive-Job | Tee-Object -FilePath $LogFile

    if ($_.State -eq "Failed") {
        Write-Host "WARNING: $($_.Name) failed!" -ForegroundColor Red
    } else {
        Write-Host "$($_.Name) completed successfully" -ForegroundColor Green
    }

    # Clean up job
    $_ | Remove-Job
}

Write-Host ""
Write-Host "All workers finished. Merging results..." -ForegroundColor Cyan

# Merge results
python scripts/analyze_pgn.py $PgnFile $OutputFile --work-dir=$WorkDir --merge

Write-Host ""
Write-Host "Done! Final output: $OutputFile" -ForegroundColor Green
Write-Host ""

# Show summary
$CompletedGames = (Get-ChildItem -Path $WorkDir -Filter "game_*.json" -ErrorAction SilentlyContinue).Count
$RemainingLocks = (Get-ChildItem -Path $WorkDir -Filter "game_*.lock" -ErrorAction SilentlyContinue).Count

Write-Host "Summary:" -ForegroundColor Cyan
Write-Host "  Completed games: $CompletedGames"
Write-Host "  Remaining locks: $RemainingLocks"

if ($RemainingLocks -gt 0) {
    Write-Host ""
    Write-Host "WARNING: Some lock files remain. This may indicate crashed workers." -ForegroundColor Yellow
    Write-Host "Review logs in $WorkDir\*.log"
}
