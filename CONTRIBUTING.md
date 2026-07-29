# Contributing

Thank you for helping improve OpenShockBot.

## Before contributing

- Treat consent and conservative physical safety limits as core requirements.
- Never include Discord tokens, OpenShock tokens, shocker UUIDs, or private Discord IDs in commits,
  tests, screenshots, issues, or logs.
- Discuss large behavioral or data-model changes in an issue before implementing them.
- Add or update tests for authorization, limit, cooldown, and device-control behavior.

## Local workflow

1. Fork the repository and create a focused branch.
2. Create a virtual environment and install `pip install -e ".[dev]"`.
3. Run `ruff check .`, `ruff format --check .`, `mypy`, and `pytest`.
4. Open a pull request explaining user-visible behavior and safety implications.

By contributing, you agree that your contribution is licensed under the MIT License.
