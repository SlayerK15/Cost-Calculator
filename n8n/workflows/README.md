# n8n Pricing Workflows

These workflow JSON files are imported into n8n to automatically fetch and update GPU and API provider pricing.

## Workflows

| File | Schedule | Description |
|------|----------|-------------|
| `aws-gpu-pricing.json` | Every 6h | Fetches AWS GPU instance pricing |
| `gcp-gpu-pricing.json` | Every 6h | Fetches GCP GPU instance pricing |
| `azure-gpu-pricing.json` | Every 6h | Fetches Azure GPU instance pricing |
| `api-provider-pricing.json` | Every 12h | Fetches OpenAI/Anthropic/Google/Mistral API pricing |

## Setup

1. Open n8n at `http://localhost:5678`
2. Login with the credentials from your `.env` file
3. Import each workflow JSON file via **Workflows > Import from File**
4. Activate each workflow

## Environment Variables

The workflows use these n8n environment variables (set in docker-compose):

- `WEBHOOK_URL` — Backend base URL (e.g., `http://backend:8000`)
- `WEBHOOK_SECRET` — Same as backend `SECRET_KEY`, used in `X-Webhook-Secret` header

## Customizing

The Code nodes in each workflow contain the pricing data. To update:

1. Edit the Code node's JavaScript
2. Update instance types, GPU specs, and pricing
3. Save and re-execute the workflow

For production, replace the hardcoded data with actual API calls:
- **AWS**: Use the AWS Price List Query API with SDK
- **GCP**: Use the Cloud Billing Catalog API
- **Azure**: The Azure Retail Prices API is already configured (just needs parsing logic)
- **API Providers**: Scrape pricing pages or use unofficial APIs
