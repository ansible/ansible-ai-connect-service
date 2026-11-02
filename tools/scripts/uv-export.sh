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
# pip --require-hashes cannot install VCS requirements. The pinned system-certifi
# fork is installed separately in wisdom-service.Containerfile.
uv export --format requirements-txt --hashes --no-emit-project --no-emit-package certifi -o requirements.txt
