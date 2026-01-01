#!/bin/bash
# Build Docker image for vast.ai deployment

set -e

echo "Building lc0-analyzer Docker image..."
docker build -t lc0-analyzer:latest .

echo ""
echo "Build complete! Next steps:"
echo ""
echo "1. Test locally (if you have NVIDIA GPU):"
echo "   docker run --gpus all -it lc0-analyzer:latest"
echo ""
echo "2. Push to Docker Hub for vast.ai:"
echo "   docker tag lc0-analyzer:latest YOUR_USERNAME/lc0-analyzer:latest"
echo "   docker login"
echo "   docker push YOUR_USERNAME/lc0-analyzer:latest"
echo ""
echo "3. See VASTAI_USAGE.md for complete instructions"
