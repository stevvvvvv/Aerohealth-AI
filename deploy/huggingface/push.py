"""Assemble the Hugging Face Space from the repo and upload it.

Usage (locally or from CI):
    HF_TOKEN=hf_xxx HF_SPACE=<user>/aerohealth-ai python deploy/huggingface/push.py
"""
from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

from huggingface_hub import HfApi

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
INCLUDE = ["frontend", "backend/aerohealth", "backend/scripts", "backend/artifacts", "backend/requirements.txt"]
IGNORE = shutil.ignore_patterns("node_modules", "dist", "__pycache__", "*.pyc", "*.db")


def main() -> None:
    space = os.environ["HF_SPACE"]
    api = HfApi(token=os.environ["HF_TOKEN"])
    api.create_repo(space, repo_type="space", space_sdk="docker", exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp)
        for item in INCLUDE:
            src, dst = ROOT / item, out / item
            dst.parent.mkdir(parents=True, exist_ok=True)
            if src.is_dir():
                shutil.copytree(src, dst, ignore=IGNORE)
            else:
                shutil.copy2(src, dst)
        shutil.copy2(HERE / "Dockerfile", out / "Dockerfile")
        shutil.copy2(HERE / "README.md", out / "README.md")
        api.upload_folder(repo_id=space, repo_type="space", folder_path=out,
                          commit_message="Deploy from GitHub", delete_patterns="*")
    print(f"Deployed: https://huggingface.co/spaces/{space}")


if __name__ == "__main__":
    main()
