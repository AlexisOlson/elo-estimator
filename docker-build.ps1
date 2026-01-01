# Build Docker image for vast.ai deployment (Windows PowerShell)

Write-Host "Building lc0-analyzer Docker image..." -ForegroundColor Green
docker build -t lc0-analyzer:latest .

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "Build complete! Next steps:" -ForegroundColor Green
    Write-Host ""
    Write-Host "1. Test locally (if you have NVIDIA GPU):"
    Write-Host "   docker run --gpus all -it lc0-analyzer:latest"
    Write-Host ""
    Write-Host "2. Push to Docker Hub for vast.ai:"
    Write-Host "   docker tag lc0-analyzer:latest alexisolson/lc0-analyzer:latest"
    Write-Host "   docker login"
    Write-Host "   docker push alexisolson/lc0-analyzer:latest"
    Write-Host ""
    Write-Host "3. See VASTAI_USAGE.md for complete instructions"
} else {
    Write-Host "Build failed!" -ForegroundColor Red
    exit 1
}
