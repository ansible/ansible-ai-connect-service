#!/bin/bash
set -o errexit

dnf install -y python3.12-devel gcc git

# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh
source $HOME/.local/bin/env

# Generate uv.lock from pyproject.toml (respects [tool.uv] settings)
uv lock --python 3.12

# Export uv.lock to requirements.txt format (--no-emit-project excludes the -e . line)
uv export --format requirements-txt --no-hashes --no-emit-project -o requirements.txt
