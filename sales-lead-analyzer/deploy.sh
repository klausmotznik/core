#!/usr/bin/env bash
# Deployment helper for Sales Lead Analyzer
# Usage: ./deploy.sh [local|docker|azure]
set -euo pipefail

MODE="${1:-local}"

case "$MODE" in
  local)
    echo "Starting backend locally..."
    cd backend
    pip install -r requirements.txt
    uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
    ;;

  docker)
    echo "Building and starting Docker container..."
    cd backend
    docker build -t sales-lead-analyzer .
    docker run -p 8000:8000 \
      -e ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY:?Set ANTHROPIC_API_KEY}" \
      -e API_KEY="${API_KEY:-}" \
      sales-lead-analyzer
    ;;

  package)
    echo "Creating Teams App Package (zip)..."
    cd appPackage
    if [ ! -f color.png ] || [ ! -f outline.png ]; then
      echo "WARNING: Icon files missing. Add color.png (192x192) and outline.png (32x32) before publishing."
    fi
    zip -r ../SalesLeadAnalyzer.zip manifest.json declarativeAgent.json salesLeadPlugin.json openapi.yaml color.png outline.png 2>/dev/null || \
    zip -r ../SalesLeadAnalyzer.zip manifest.json declarativeAgent.json salesLeadPlugin.json openapi.yaml
    echo "Package created: SalesLeadAnalyzer.zip"
    echo ""
    echo "Next steps:"
    echo "  1. Update 'YOUR_BACKEND_URL' in openapi.yaml and salesLeadPlugin.json"
    echo "  2. Upload SalesLeadAnalyzer.zip in Microsoft Teams Admin Center"
    echo "     or via Teams Toolkit in VS Code"
    ;;

  *)
    echo "Usage: $0 [local|docker|package]"
    exit 1
    ;;
esac
