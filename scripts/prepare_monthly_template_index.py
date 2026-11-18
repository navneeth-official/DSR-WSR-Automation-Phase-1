"""
One-time helper: copy the Index slide from the weekly WSR template into the monthly
cadence template (after the cover slide). Uses PowerPoint COM on Windows.

    python scripts/prepare_monthly_template_index.py

After this, generate_monthly_report.py uses the Index already in templates/monthly/
and does not import from the WSR file at runtime (avoids corrupt .pptx saves).
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT if (_REPO_ROOT := _REPO) else _REPO))

from monthly_report.config import resolve_index_reference, resolve_template
from monthly_report.index_slide import find_index_slide_index


def main() -> None:
    try:
        import win32com.client  # type: ignore
    except ImportError as exc:
        raise SystemExit("pywin32 required: pip install pywin32") from exc

    monthly_path = resolve_template()
    wsr_path = resolve_index_reference()

    existing = find_index_slide_index(__import__("pptx").Presentation(str(monthly_path)))
    if existing == 1:
        print(f"Index slide already at slide 2 in {monthly_path}")
        return

    ppt = win32com.client.Dispatch("PowerPoint.Application")
    wsr = ppt.Presentations.Open(str(wsr_path.resolve()), ReadOnly=True)
    monthly = ppt.Presentations.Open(str(monthly_path.resolve()), ReadOnly=False)
    try:
        wsr_index = find_index_slide_index(__import__("pptx").Presentation(str(wsr_path))) or 1
        wsr.Slides(wsr_index + 1).Copy()
        monthly.Slides.Paste(Index=2)
        monthly.SaveAs(str(monthly_path.resolve()))
        print(f"Inserted Index slide into {monthly_path}")
    finally:
        monthly.Close()
        wsr.Close()
        ppt.Quit()


if __name__ == "__main__":
    main()
