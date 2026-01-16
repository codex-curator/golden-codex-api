# Contributing to Golden Codex API

Thank you for your interest in contributing to the Golden Codex API SDKs and documentation!

## Ways to Contribute

- **Bug Reports**: Found a bug? Open an issue with details.
- **Feature Requests**: Have an idea? We'd love to hear it.
- **Documentation**: Improvements to docs are always welcome.
- **SDK Improvements**: Bug fixes and enhancements to the SDKs.

## Development Setup

### Node.js SDK

```bash
cd sdks/node
npm install
npm run build
npm test
```

### Python SDK

```bash
cd sdks/python
pip install -e ".[dev]"
pytest
mypy golden_codex
ruff check golden_codex
```

## Submitting Changes

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Make your changes
4. Run tests and linting
5. Commit with a clear message
6. Push to your fork
7. Open a Pull Request

## Code Style

### Node.js

- TypeScript with strict mode
- ESLint for linting
- Prettier for formatting

### Python

- Python 3.9+ compatible
- Type hints throughout
- Ruff for linting
- Black-compatible formatting

## Questions?

- Open a GitHub issue
- Email: api@golden-codex.com
- Discord: [Join our community](https://discord.gg/goldencodex)

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
