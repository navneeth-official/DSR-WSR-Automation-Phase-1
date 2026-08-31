"""Adapter: build PPTX via the existing update_delivery_status layout engine."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from app.paths import PPT_BUILDER, REPO_ROOT, SCRIPTS_DIR


class SubprocessDeckGenerator:
    """
    Invokes ``update_delivery_status.py`` without modifying its spacing logic.

    This preserves the current estimate-based layout engine as the initial
    deck builder; vision correction runs in later pipeline stages.
    """

    def __init__(self, builder_script: Path | None = None) -> None:
        self._builder = builder_script or PPT_BUILDER

    def generate(
        self,
        content_json: Path,
        output_ppt: Path,
        *,
        layout_hints: Path | None = None,
    ) -> Path:
        if not self._builder.is_file():
            raise FileNotFoundError(f"PPT builder not found: {self._builder}")
        if not content_json.is_file():
            raise FileNotFoundError(f"Content JSON not found: {content_json}")

        cmd = [
            sys.executable,
            str(self._builder),
            "--content",
            str(content_json.resolve()),
            "--output",
            str(output_ppt.resolve()),
        ]
        if layout_hints and layout_hints.is_file():
            cmd.extend(["--layout-hints", str(layout_hints.resolve())])

        subprocess.run(cmd, cwd=str(REPO_ROOT), check=True)
        return output_ppt.resolve()
