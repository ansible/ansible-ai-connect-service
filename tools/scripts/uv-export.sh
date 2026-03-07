#!/bin/bash
set -o errexit

dnf install -y python3.12-devel gcc git

# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh
source $HOME/.local/bin/env

# Export the committed uv.lock to requirements.txt format for the Linux target platform.
# Do NOT run `uv lock` here — uv.lock is cross-platform and must be resolved locally
# (via `uv lock`) and committed before running this script. Re-resolving inside the
# container would override pyproject.toml changes with Linux-specific resolutions.
uv export --format requirements-txt --no-hashes --no-emit-project -o requirements.txt
