"""Probe configured LLM provider (Gemini / Azure / OpenAI / Bedrock). No secrets printed."""
from __future__ import annotations

import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO))

from dotenv import load_dotenv

load_dotenv(_REPO / ".env")

# Fresh settings after dotenv
from app.config import get_settings

get_settings.cache_clear()

from app.services.llm_client import create_llm_client, dump_llm_config


def main() -> None:
    info = dump_llm_config()
    for key, value in info.items():
        print(f"{key}: {value}")

    client, model = create_llm_client()
    if client is None:
        print("create_llm_client: no client (missing credentials for resolved provider)")
        return

    print(f"client type: {type(client).__name__}")
    print(f"model: {model!r}")
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "Reply with OK"}],
            max_tokens=8,
        )
        text = (resp.choices[0].message.content or "").strip()
        print(f"call ok: {text!r}")
    except Exception as exc:  # noqa: BLE001
        print(f"call failed: {type(exc).__name__}: {exc}")


if __name__ == "__main__":
    main()
