import os

from .base import *  # NOQA

DEBUG = True

ANSIBLE_WISDOM_AI_CHECKPOINT_PATH = os.path.join(
    BASE_DIR, "..", "..", ".checkpoint", "latest"  # NOQA
)
