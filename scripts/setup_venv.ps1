param(
  [string]$venvPath = ".venv"
)
Write-Host "Creating virtual environment at $venvPath"

# Resolve repository root relative to this script
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$repoRoot = Resolve-Path (Join-Path $scriptDir "..")
$venvFull = Join-Path $repoRoot $venvPath

python -m venv "$venvFull"
$activate = Join-Path $venvFull "Scripts\Activate.ps1"
if (Test-Path $activate) {
  Write-Host "Activating venv and installing requirements"
  # Activate in this process so subsequent python invocations use the venv
  & "$activate"
  python -m pip install --upgrade pip
  # Prefer per-script requirements in scripts/ for this repo
  $req = Join-Path $repoRoot "scripts\requirements.txt"
  if (Test-Path $req) {
    Write-Host "Installing dependencies from $req"
    python -m pip install -r "$req"
  } else {
    Write-Host "requirements not found at $req; skipping pip install -r"
  }
  Write-Host "Done. To activate the venv in PowerShell run: .\$venvPath\Scripts\Activate.ps1"
} else {
  Write-Host "Activation script not found; created venv but please activate manually."
}
