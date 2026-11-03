"""Build a WSR deck from the placeholder sample slide."""

from __future__ import annotations

from pathlib import Path

from app.services.wsr_template import resolve_wsr_template
from app.wsr_engine.main import WsrEngine


class SubprocessDeckGenerator:
    """Rebuild a deck with the placeholder-template engine."""

    def generate(
        self,
        content_json: Path,
        output_ppt: Path,
        *,
        layout_hints: Path | None = None,
        template: Path | str | None = None,
    ) -> Path:
        del layout_hints
        if not content_json.is_file():
            raise FileNotFoundError(f"Content JSON not found: {content_json}")

        report = WsrEngine().run(
            template_path=resolve_wsr_template(template),
            content_path=content_json,
            output_path=output_ppt,
        )
        if report.errors:
            raise RuntimeError(f"WSR engine errors: {report.errors}")
        return Path(report.output_path).resolve()
