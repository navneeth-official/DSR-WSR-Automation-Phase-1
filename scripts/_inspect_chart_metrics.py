import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pptx import Presentation
from pptx.oxml.ns import qn
from monthly_report.tokens import TOKEN_RE, token_key
from monthly_report.delivery_slide import (
    METRIC_KEYS,
    find_delivery_slide,
    analyze_delivery_slide,
    _series_metrics_for_chart,
    _series_metric_fallback,
)
from monthly_report.metrics import ENDED, IN_PROGRESS, SprintMetrics
from datetime import date

for tp in [
    ROOT / "templates" / "G10X_H-E-B_MSR_Template_two.pptx",
    ROOT / "G10X_H-E-B_MSR_Template_two.pptx",
]:
    if not tp.is_file():
        continue
    prs = Presentation(str(tp))
    slide = find_delivery_slide(prs)
    t = analyze_delivery_slide(slide)
    ch = t.chart_frame.chart
    print("===", tp.name, "metric_labels", t.metric_labels, "===")
    for series in ch.plots[0].series:
        found_first = None
        all_tokens = []
        for el in series._element.iter():
            text = el.text or ""
            for raw in TOKEN_RE.findall(text):
                key = token_key(raw)
                if key in METRIC_KEYS:
                    all_tokens.append((key, el.tag.split("}")[-1]))
                    if found_first is None:
                        found_first = key
        print(
            series.name,
            "first_token", found_first,
            "fallback", _series_metric_fallback(series.name, t.metric_labels),
            "tokens", all_tokens[:12],
        )
    names = [s.name for s in ch.plots[0].series]
    print("resolved", _series_metrics_for_chart(ch, names, t.metric_labels))
