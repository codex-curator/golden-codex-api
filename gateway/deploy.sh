#!/bin/bash
# Deploy Golden Codex API Gateway to Cloud Run

set -e

# Configuration
PROJECT_ID="the-golden-codex-1111"
REGION="us-west1"
SERVICE_NAME="api-gateway"
IMAGE_NAME="gcr.io/${PROJECT_ID}/api-gateway"

echo "🚀 Deploying Golden Codex API Gateway..."
echo "   Project: ${PROJECT_ID}"
echo "   Region: ${REGION}"
echo "   Service: ${SERVICE_NAME}"

# Build and push image
echo "📦 Building Docker image..."
gcloud builds submit \
    --project=${PROJECT_ID} \
    --tag=${IMAGE_NAME}:latest \
    .

# Deploy to Cloud Run
echo "☁️  Deploying to Cloud Run..."
gcloud run deploy ${SERVICE_NAME} \
    --project=${PROJECT_ID} \
    --region=${REGION} \
    --image=${IMAGE_NAME}:latest \
    --platform=managed \
    --allow-unauthenticated \
    --memory=512Mi \
    --cpu=1 \
    --timeout=300 \
    --concurrency=100 \
    --min-instances=1 \
    --max-instances=10 \
    --set-env-vars="GCP_PROJECT=${PROJECT_ID},FIRESTORE_DATABASE=golden-codex-database,ENVIRONMENT=production"

# Get the service URL
SERVICE_URL=$(gcloud run services describe ${SERVICE_NAME} \
    --project=${PROJECT_ID} \
    --region=${REGION} \
    --format='value(status.url)')

echo ""
echo "✅ Deployment complete!"
echo "   Service URL: ${SERVICE_URL}"
echo ""
echo "🔗 API Endpoints:"
echo "   Health:  ${SERVICE_URL}/health"
echo "   Docs:    ${SERVICE_URL}/docs"
echo "   OpenAPI: ${SERVICE_URL}/openapi.json"
echo ""
echo "📝 Next steps:"
echo "   1. Set up custom domain: api.golden-codex.com"
echo "   2. Configure Cloud Armor for DDoS protection"
echo "   3. Set up uptime monitoring"
