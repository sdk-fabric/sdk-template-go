#!/usr/bin/env python3
"""Syncs boilerplate wrapper files from a template directory into the root repository,

replacing JSON metadata placeholders dynamically.
"""

import argparse
import json
import shutil
import sys
from pathlib import Path


def is_binary(file_path: Path) -> bool:
    """Detect binary files by checking for NULL bytes in the first chunk."""
    try:
        with open(file_path, "rb") as f:
            chunk = f.read(1024)
            return b"\x00" in chunk
    except OSError:
        return False


def load_replacements(config_path: Path) -> dict[str, str]:
    """Parse JSON metadata and GitHub environment variables into placeholder mappings."""
    data = {}

    # 1. Load local .sdk-fabric.json if available
    if config_path.is_file():
        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)

    # 2. Inject environment metadata automatically if running in GitHub Actions
    server_url = os.getenv("GITHUB_SERVER_URL", "https://github.com")
    repo_slug = os.getenv("GITHUB_REPOSITORY", "")  # e.g., "sdk-fabric/petstore-java"

    if repo_slug and "/" in repo_slug:
        user_name, repo_name = repo_slug.split("/", 1)

        # Set variables using setdefault (won't overwrite if explicitly defined in .sdk-fabric.json)
        data.setdefault("github_user", user_name)        # e.g. "sdk-fabric"
        data.setdefault("github_repository", repo_name)        # e.g. "petstore-java"
        data.setdefault("github_url", f"{server_url}/{repo_slug}")  # e.g. "https://github.com/sdk-fabric/petstore-java"

    return {
        f"{{{{{key}}}}}": str(val)
        for key, val in data.items()
        if not isinstance(val, (dict, list))
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync template files to repository root.")
    parser.add_argument("--template-dir", type=Path, default=Path(".template_tmp"))
    parser.add_argument("--config-file", type=Path, default=Path(".sdk-fabric.json"))
    args = parser.parse_args()

    template_dir: Path = args.template_dir
    config_file: Path = args.config_file

    # 1. Validation
    if not config_file.is_file():
        print(f"Config file '{config_file}' not found.")
        sys.exit(1)

    if not template_dir.is_dir():
        print(f"Template directory '{template_dir}' not found.")
        sys.exit(1)

    # 2. Load placeholders
    replacements = load_replacements(config_file)

    # 3. Process template files using pathlib
    ignored_parts = {".git", ".sdk-fabric.json", "sync.py"}

    for src_file in template_dir.rglob("*"):
        if not src_file.is_file():
            continue

        rel_path = src_file.relative_to(template_dir)

        # Skip ignored directories or files
        if any(part in ignored_parts for part in rel_path.parts):
            continue

        dest_file = Path(rel_path)
        dest_file.parent.mkdir(parents=True, exist_ok=True)

        # 4. Copy binary or render text
        if is_binary(src_file):
            shutil.copy2(src_file, dest_file)
        else:
            try:
                content = src_file.read_text(encoding="utf-8")
                for placeholder, value in replacements.items():
                    content = content.replace(placeholder, value)
                dest_file.write_text(content, encoding="utf-8")
            except UnicodeDecodeError:
                # Fallback for unexpected encoding issues
                shutil.copy2(src_file, dest_file)

    print("Template sync completed successfully.")


if __name__ == "__main__":
    main()
