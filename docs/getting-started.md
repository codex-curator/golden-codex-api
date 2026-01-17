# Getting Started

This guide will help you get up and running with the Golden Codex API in under 5 minutes.

## Prerequisites

- A Golden Codex account ([sign up free](https://golden-codex.com/signup))
- Node.js 18+ or Python 3.9+

## Step 1: Get Your API Key

1. Log in to [golden-codex.com](https://golden-codex.com)
2. Navigate to **Dashboard** > **API Keys**
3. Click **Create New Key**
4. Give it a name (e.g., "Development")
5. Copy the key immediately - it won't be shown again!

Your API key looks like: `gcx_live_Abc123XyzDef456...`

> **Security Note**: Never commit API keys to version control. Use environment variables instead.

## Step 2: Install an SDK

### Node.js

```bash
npm install @golden-codex/sdk
```

### Python

```bash
pip install golden-codex
```

## Step 3: Process Your First Image

### Node.js

```typescript
import { GoldenCodex } from '@golden-codex/sdk';

const gcx = new GoldenCodex({
  apiKey: process.env.GOLDEN_CODEX_API_KEY
});

async function enhanceImage() {
  // Create a job
  const job = await gcx.jobs.create({
    imageUrl: 'https://example.com/artwork.jpg',
    operations: ['nova', 'flux', 'atlas']
  });

  console.log(`Job created: ${job.jobId}`);
  console.log(`Estimated cost: ${job.cost.estimatedAet} GCX`);

  // Wait for completion (polls automatically)
  const result = await gcx.jobs.wait(job.jobId);

  console.log('Done!');
  console.log('AI-generated title:', result.results.goldenCodex.title);
  console.log('Final image URL:', result.results.urls.final);
}

enhanceImage();
```

### Python

```python
import os
from golden_codex import GoldenCodex

gcx = GoldenCodex(api_key=os.environ["GOLDEN_CODEX_API_KEY"])

# Create a job
job = gcx.jobs.create(
    image_url="https://example.com/artwork.jpg",
    operations=["nova", "flux", "atlas"]
)

print(f"Job created: {job['job_id']}")
print(f"Estimated cost: {job['cost']['estimated_gcx']} GCX")

# Wait for completion
result = gcx.jobs.wait(job["job_id"])

print("Done!")
print("AI-generated title:", result["results"]["golden_codex"]["title"])
print("Final image URL:", result["results"]["urls"]["final"])
```

## Step 4: Understanding the Response

A completed job returns rich results:

```json
{
  "job_id": "job_7f3d8a2b1c4e",
  "status": "completed",
  "results": {
    "golden_codex": {
      "title": "Crimson Tide at Dusk",
      "artist_interpretation": "A meditation on transition...",
      "style_classification": ["impressionism", "landscape"],
      "color_analysis": {
        "dominant": ["#8B0000", "#FFD700"],
        "mood": "dramatic"
      },
      "soul_whisper": "I am the moment between breaths..."
    },
    "urls": {
      "original": "https://cdn.golden-codex.com/.../original.jpg",
      "upscaled": "https://cdn.golden-codex.com/.../upscaled.png",
      "final": "https://cdn.golden-codex.com/.../final.png"
    }
  }
}
```

## Understanding Operations

| Operation | What It Does | Cost |
|-----------|-------------|------|
| `nova` | AI analyzes image and generates 50+ metadata fields | 1-2 GCX |
| `flux` | Upscales image 2-4x using ESRGAN | 1-2 GCX |
| `atlas` | Embeds metadata into image file (XMP/EXIF) | 1 GCX |

You can run any combination:

```typescript
// Just metadata, no upscaling
await gcx.jobs.create({
  imageUrl: '...',
  operations: ['nova', 'atlas']
});

// Just upscaling, no metadata
await gcx.jobs.create({
  imageUrl: '...',
  operations: ['flux']
});
```

## Next Steps

- [API Reference](./endpoints/jobs.md) - Full endpoint documentation
- [Webhooks](./endpoints/webhooks.md) - Get notified when jobs complete
- [Error Handling](./errors.md) - Handle errors gracefully
- [Rate Limits](./rate-limits.md) - Understand usage limits

## Get Help

- **Email**: api@golden-codex.com
- **Discord**: [Join our community](https://discord.gg/goldencodex)
- **GitHub Issues**: [Report a bug](https://github.com/codex-curator/golden-codex-api/issues)
