"""HTTP client for a remote Windows PowerPoint COM render service."""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path
from typing import Sequence

import requests


class RemoteSlideRendererBackend:
    """
    Sends PPTX to a Windows machine running ``scripts/ppt_render_server.py``.

    Uses real PowerPoint COM on the remote host — pixel-accurate previews on Linux VMs.
    """

    def __init__(
        self,
        *,
        base_url: str,
        token: str | None = None,
        timeout_sec: int = 300,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._token = token
        self._timeout_sec = timeout_sec

    def render_slides(
        self,
        ppt_path: Path,
        output_dir: Path,
        *,
        slide_indices: Sequence[int] | None = None,
        width_px: int = 1920,
    ) -> list[Path]:
        ppt_path = ppt_path.resolve()
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        url = f"{self._base_url}/render-slides"
        headers: dict[str, str] = {}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"

        data: dict[str, str] = {"width_px": str(width_px)}
        if slide_indices is not None:
            data["slide_indices"] = json.dumps(list(slide_indices))

        with ppt_path.open("rb") as handle:
            response = requests.post(
                url,
                headers=headers,
                data=data,
                files={
                    "file": (
                        ppt_path.name,
                        handle,
                        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                    )
                },
                timeout=self._timeout_sec,
            )

        if response.status_code >= 400:
            detail = response.text.strip() or f"HTTP {response.status_code}"
            raise RuntimeError(
                f"Remote slide render failed ({response.status_code}): {detail}"
            )

        content_type = (response.headers.get("content-type") or "").lower()
        if "zip" not in content_type and not response.content[:2] == b"PK":
            raise RuntimeError(
                "Remote render service did not return a ZIP of PNG slides. "
                f"Content-Type: {content_type or 'unknown'}"
            )

        exported: list[Path] = []
        with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
            names = sorted(
                (n for n in archive.namelist() if n.lower().endswith(".png")),
                key=_slide_name_sort_key,
            )
            if not names:
                raise RuntimeError("Remote render returned an empty ZIP (no PNG files)")

            for name in names:
                filename = Path(name).name
                target = (output_dir / filename).resolve()
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(archive.read(name))
                exported.append(target)

        if slide_indices is not None:
            wanted = {int(i) for i in slide_indices}
            exported = [
                p
                for p in exported
                if _slide_index_from_name(p.name) in wanted
            ]

        return sorted(exported, key=lambda p: _slide_index_from_name(p.name))


def _slide_index_from_name(name: str) -> int:
    stem = Path(name).stem
    if "_" in stem:
        try:
            return int(stem.split("_", 1)[1])
        except ValueError:
            pass
    return 0


def _slide_name_sort_key(name: str) -> int:
    return _slide_index_from_name(Path(name).name)
