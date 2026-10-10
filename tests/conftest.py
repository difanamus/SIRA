"""Tests start from an empty knowledge base unless a test applies the seed explicitly."""

import os

os.environ["SIRA_SEED_KB"] = "false"
