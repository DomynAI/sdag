# Contributing to sdag

Thank you for your interest in contributing to sdag!

### Linting and Formatting

Linting and formatting are managed by [ruff](https://docs.astral.sh/ruff/).
The official documentation will help you download and configure it for your editor.

### editorconfig

We use [editorconfig](https://editorconfig.org/) to maintain a consistent style across different file formats.

### Pre-commit

Git hooks are managed through [pre-commit](https://pre-commit.com/). You can install it tool with uv:

```sh
uv tool install pre-commit
```

and use it to install all hooks:

```sh
pre-commit install
```

### Type checking

It's done with [pyright](https://microsoft.github.io/pyright/#/), the hook will run automatically after every commit if properly installed.

## Code

If possible, try to follow the existing conventions. The linter will greatly help you highlight inconsistencies.

## Pull Requests

We welcome pull requests and help you throughout the process. PRs should follow the standard workflow:

- Fork the repository starting from the main branch
- Add tests if you've added code that requires testing.
- Update the documentation if required.
- Ensure all Python and Rust tests pass
- Run the git hooks via `pre-commit run --all-files` to verify your code is correctly formatted, linted, and type checked.
