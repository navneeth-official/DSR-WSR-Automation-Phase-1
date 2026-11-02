from lxml import etree

from monthly_report.tokens import replace_tokens_in_paragraph, token_key

_A = "http://schemas.openxmlformats.org/drawingml/2006/main"


def _paragraph(*runs: tuple[str, str]):
    body = "".join(
        f'<a:r><a:rPr lang="en-US" b="{bold}"/><a:t>{text}</a:t></a:r>' for text, bold in runs
    )
    return etree.fromstring(f'<a:p xmlns:a="{_A}">{body}</a:p>')


def _runs(p):
    return [
        (r.find(f"{{{_A}}}t").text, r.find(f"{{{_A}}}rPr").get("b"))
        for r in p.findall(f"{{{_A}}}r")
    ]


def test_token_key_normalizes_numbered_and_spaced_names():
    assert token_key("Sprint Name 1") == "sprint_name"
    assert token_key("Sprint Name 3") == "sprint_name"
    assert token_key("Sprint 2") == "sprint"
    assert token_key("Start date") == "start_date"
    assert token_key(" TC ") == "tc"


def test_replaces_token_inside_single_run_keeping_static_text():
    p = _paragraph(("Bi-week Level Snapshot – {{Sprint Name 1}}", "1"))
    assert replace_tokens_in_paragraph(p, {"sprint_name": "Q3.05 FY26 Perseus"}) == []
    assert _runs(p) == [("Bi-week Level Snapshot – Q3.05 FY26 Perseus", "1")]


def test_token_split_across_runs_takes_format_of_token_name_run():
    p = _paragraph(("Snapshot {{", "0"), ("Sprint Name 3", "1"), ("}} end", "0"))
    replace_tokens_in_paragraph(p, {"sprint_name": "Atlas"})
    assert _runs(p) == [("Snapshot ", "0"), ("Atlas", "1"), (" end", "0")]


def test_multiple_tokens_in_one_paragraph():
    p = _paragraph(("{{Start date}}\u00a0–{{End date}}, {{Status}} ", "0"))
    replace_tokens_in_paragraph(
        p, {"start_date": "Aug 03", "end_date": "Aug 14", "status": "Ended"}
    )
    assert _runs(p) == [("Aug 03\u00a0–Aug 14, Ended ", "0")]


def test_unknown_tokens_are_left_and_reported():
    p = _paragraph(("{{RCA}} and {{TC}}", "0"))
    assert replace_tokens_in_paragraph(p, {"tc": "4"}) == ["{{RCA}}"]
    assert _runs(p) == [("{{RCA}} and 4", "0")]
