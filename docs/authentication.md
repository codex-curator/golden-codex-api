# Authentication

The Golden Codex API uses API keys for authentication. All requests must include your API key in the `Authorization` header.

## API Key Format

API keys have a structured format:

```
gcx_live_Abc123XyzDef456GhiJkl789Mno012Pqr
└─┬─┘└┬─┘└────────────────┬────────────────┘
  │   │                   │
  │   │                   └─ 36 random characters
  │   └─ Environment (live or test)
  └─ Prefix identifier
```

- **Live keys** (`gcx_live_...`) - For production use, charges real credits
- **Test keys** (`gcx_test_...`) - For development, uses sandbox environment

## Making Authenticated Requests

Include your API key in the `Authorization` header:

```bash
curl https://api.golden-codex.com/v1/jobs \
  -H "Authorization: Bearer gcx_live_your_key_here" \
  -H "Content-Type: application/json" \
  -d '{"image_url": "https://example.com/image.jpg"}'
```

### SDK Authentication

```typescript
// Node.js
const gcx = new GoldenCodex({
  apiKey: process.env.GOLDEN_CODEX_API_KEY
});
```

```python
# Python
gcx = GoldenCodex(api_key=os.environ["GOLDEN_CODEX_API_KEY"])
```

## Managing API Keys

### Creating a Key

1. Go to [Dashboard > API Keys](https://golden-codex.com/dashboard/api-keys)
2. Click **Create New Key**
3. Name your key (e.g., "Production Server", "Local Dev")
4. Copy the key immediately

> **Important**: The full API key is only shown once at creation. Store it securely.

### Revoking a Key

1. Go to [Dashboard > API Keys](https://golden-codex.com/dashboard/api-keys)
2. Find the key to revoke
3. Click **Revoke**
4. Confirm the action

Revoked keys immediately stop working. Create a new key before revoking if needed.

### Key Permissions

Currently, all API keys have full access to your account's resources. Fine-grained permissions are coming soon.

## Security Best Practices

### Do

- Store keys in environment variables
- Use different keys for development and production
- Rotate keys periodically
- Revoke unused keys

### Don't

- Commit keys to version control
- Share keys in public forums
- Embed keys in client-side code
- Log keys in application logs

### Environment Variables

```bash
# .env file (add to .gitignore!)
GOLDEN_CODEX_API_KEY=gcx_live_your_key_here
```

```typescript
// Node.js
const apiKey = process.env.GOLDEN_CODEX_API_KEY;
if (!apiKey) {
  throw new Error('GOLDEN_CODEX_API_KEY not set');
}
```

```python
# Python
import os
api_key = os.environ.get("GOLDEN_CODEX_API_KEY")
if not api_key:
    raise ValueError("GOLDEN_CODEX_API_KEY not set")
```

## Error Responses

### Invalid or Missing Key

```json
HTTP 401 Unauthorized

{
  "error": {
    "code": "invalid_api_key",
    "message": "API key is invalid or has been revoked"
  }
}
```

### Revoked Key

```json
HTTP 401 Unauthorized

{
  "error": {
    "code": "api_key_revoked",
    "message": "This API key has been revoked"
  }
}
```

## Account Linking

API keys are linked to your Golden Codex account. All operations:

- Use your account's GCX balance
- Count toward your rate limits
- Appear in your usage dashboard

Multiple keys share the same account resources.
