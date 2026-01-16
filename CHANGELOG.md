# Changelog

All notable changes to the Golden Codex API and SDKs will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-01-16

### Added

- Initial public release of Golden Codex API v1
- Node.js SDK (`@golden-codex/sdk`)
- Python SDK (`golden-codex`)
- Full documentation
- OpenAPI 3.0 specification

### Features

- **Jobs API**: Create, list, get, cancel enhancement jobs
- **Operations**: Nova (AI metadata), Flux (upscaling), Atlas (infusion)
- **Account API**: Balance, usage statistics
- **Webhooks**: Event subscriptions with signature verification
- **Cost Estimation**: Calculate costs before creating jobs

### SDKs

- TypeScript/Node.js with full type definitions
- Python with sync and async clients
- Automatic retry for rate limits
- Webhook signature verification utilities
