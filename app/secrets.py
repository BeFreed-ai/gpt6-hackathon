"""Load provider-specific secrets without logging or crossing credential boundaries."""

from __future__ import annotations

import json
import os
import subprocess


def openai_api_key() -> str | None:
    return _api_key("OPENAI")


def novita_api_key() -> str | None:
    return _api_key("NOVITA")


def _api_key(provider: str) -> str | None:
    if os.environ.get(f"{provider}_API_KEY", "").strip():
        return os.environ[f"{provider}_API_KEY"].strip()
    secret_id = os.environ.get(f"{provider}_SECRET_ID")
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
        field = os.environ.get(f"{provider}_SECRET_FIELD", f"{provider}_API_KEY")
        key = value.get(field) if isinstance(value, dict) else value
        if not isinstance(key, str) or not key.strip():
            raise ValueError("Missing credential")
        return key.strip()
    except Exception:
        raise RuntimeError(f"Unable to load the configured {provider} secret from AWS.") from None
