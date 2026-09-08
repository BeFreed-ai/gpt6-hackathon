"""Load an explicitly configured OpenAI secret without logging credential values."""

from __future__ import annotations

import json
import os
import subprocess


def openai_api_key() -> str | None:
    if os.environ.get("OPENAI_API_KEY"):
        return os.environ["OPENAI_API_KEY"]
    secret_id = os.environ.get("OPENAI_SECRET_ID")
    if not secret_id:
        return None
    command = [
        "aws",
        "secretsmanager",
        "get-secret-value",
        "--secret-id",
        secret_id,
        "--output",
        "json",
        "--no-cli-pager",
    ]
    if os.environ.get("AWS_REGION"):
        command.extend(["--region", os.environ["AWS_REGION"]])
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=True, timeout=30)
        secret = json.loads(result.stdout)["SecretString"]
        try:
            value = json.loads(secret)
        except json.JSONDecodeError:
            value = secret
        key = value.get("OPENAI_API_KEY") if isinstance(value, dict) else value
        if not isinstance(key, str) or not key.strip():
            raise ValueError("Missing credential")
        return key.strip()
    except Exception:
        raise RuntimeError("Unable to load the configured OpenAI secret from AWS.") from None
