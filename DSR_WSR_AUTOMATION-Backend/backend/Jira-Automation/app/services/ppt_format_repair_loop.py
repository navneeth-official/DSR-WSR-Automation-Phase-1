"""Orchestrate extract → detect → plan → repair loop until deck passes or max rounds."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.services.ppt_format_evaluator import evaluate_deck_format, load_rulebook
from app.services.ppt_format_extractor import extract_deck
from app.services.ppt_format_fix_planner import plan_fixes
from app.services.ppt_format_repair import apply_fix_plan, run_full_rebuild
from app.services.ppt_format_violations import detect_deck_violations


@dataclass
class RepairResult:
    ppt_path: Path
    rounds: list[dict[str, Any]] = field(default_factory=list)
    final_violations: dict[str, Any] | None = None
    final_evaluation: dict[str, Any] | None = None
    passed: bool = False
    repair_log_path: Path | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "ppt_path": str(self.ppt_path),
            "passed": self.passed,
            "rounds": self.rounds,
            "final_violations": self.final_violations,
            "final_evaluation": self.final_evaluation,
            "repair_log_path": str(self.repair_log_path) if self.repair_log_path else None,
        }


def _eval_has_open_issues(evaluation: dict[str, Any] | None) -> bool:
    """True when any slide still has violations or fails per-slide pass."""
    if not evaluation:
        return False
    for slide in evaluation.get("slides", []):
        if slide.get("violations"):
            return True
        if not slide.get("pass", True):
            return True
    return False


def _should_stop(
    violations_report: dict[str, Any],
    evaluation: dict[str, Any] | None,
    *,
    require_eval: bool,
    fix_all: bool,
) -> bool:
    """Stop only when every deterministic violation is cleared and eval is clean."""
    if violations_report.get("violation_count", 0) > 0:
        return False
    if not require_eval or not fix_all:
        return True
    if evaluation is None:
        return True
    return not _eval_has_open_issues(evaluation)


def repair_deck_until_pass(
    ppt_path: str | Path,
    content_json_path: str | Path,
    *,
    max_rounds: int = 5,
    pass_threshold: float = 80,
    run_evaluation: bool = False,
    rulebook_path: Path | None = None,
    fix_all: bool = True,
    scope_all_slides: bool = True,
) -> RepairResult:
    """
    Run repair loop until ALL deterministic violations are fixed.
    Saves {ppt}.repair_log.json alongside the deck.

    Pass ``run_evaluation=True`` only for legacy AI rulebook re-check (deprecated).
    v2.0 repair pass/fail is driven solely by ``detect_deck_violations``.
    """
    ppt_path = Path(ppt_path)
    content_json_path = Path(content_json_path)
    load_rulebook(rulebook_path)

    result = RepairResult(ppt_path=ppt_path)
    require_eval = run_evaluation and fix_all
    content_titles: set[str] | None = None
    if content_json_path.is_file():
        with open(content_json_path, encoding="utf-8") as f:
            content = json.load(f)
        content_titles = {
            s.get("title", "") for s in content.get("slides", []) if s.get("title")
        }

    for round_num in range(1, max_rounds + 1):
        deck_data = extract_deck(ppt_path)
        violations_report = detect_deck_violations(
            deck_data,
            content_titles=content_titles,
            scope_all_slides=scope_all_slides,
        )

        evaluation: dict[str, Any] | None = None
        eval_error: str | None = None
        if run_evaluation:
            try:
                evaluation = evaluate_deck_format(ppt_path, rulebook_path)
            except Exception as exc:  # noqa: BLE001
                eval_error = str(exc)
                require_eval = False

        round_info: dict[str, Any] = {
            "round": round_num,
            "violation_count": violations_report.get("violation_count", 0),
            "critical_count": violations_report.get("critical_count", 0),
            "violations": violations_report.get("violations", []),
            "deck_score": evaluation.get("deck_score") if evaluation else None,
            "deck_pass": evaluation.get("deck_pass") if evaluation else None,
            "eval_open_issues": _eval_has_open_issues(evaluation) if evaluation else None,
            "eval_error": eval_error,
            "actions": [],
        }

        if _should_stop(
            violations_report,
            evaluation,
            require_eval=require_eval,
            fix_all=fix_all,
        ):
            round_info["stopped"] = "all_clear"
            result.rounds.append(round_info)
            result.final_violations = violations_report
            result.final_evaluation = evaluation
            result.passed = True
            break

        violation_count = violations_report.get("violation_count", 0)
        eval_issues = _eval_has_open_issues(evaluation) if evaluation else False

        if violation_count == 0 and not eval_issues:
            round_info["stopped"] = "all_clear"
            result.rounds.append(round_info)
            result.final_violations = violations_report
            result.final_evaluation = evaluation
            result.passed = True
            break

        # Last resort: full rebuild then in-place cleanup for remaining issues.
        if round_num >= max_rounds and content_json_path.is_file():
            round_info["actions"] = {"full_rebuild": True}
            run_full_rebuild(content_json_path, ppt_path)
            deck_data = extract_deck(ppt_path)
            violations_report = detect_deck_violations(
                deck_data,
                content_titles=content_titles,
                scope_all_slides=scope_all_slides,
            )
            if violations_report.get("violation_count", 0) > 0:
                from app.services.ppt_format_fix_planner import _deterministic_fallback

                cleanup_plan = _deterministic_fallback(violations_report["violations"])
                apply_fix_plan(
                    ppt_path,
                    cleanup_plan,
                    content_json=content_json_path,
                )
                deck_data = extract_deck(ppt_path)
                violations_report = detect_deck_violations(
                    deck_data,
                    content_titles=content_titles,
                    scope_all_slides=scope_all_slides,
                )
            round_info["post_rebuild_violations"] = violations_report.get(
                "violation_count", 0
            )
            result.rounds.append(round_info)
            result.final_violations = violations_report
            if run_evaluation:
                try:
                    result.final_evaluation = evaluate_deck_format(ppt_path, rulebook_path)
                except Exception:  # noqa: BLE001
                    result.final_evaluation = evaluation
            else:
                result.final_evaluation = evaluation
            result.passed = _should_stop(
                result.final_violations,
                result.final_evaluation,
                require_eval=require_eval,
                fix_all=fix_all,
            )
            break

        if violation_count == 0 and eval_issues and round_num >= max_rounds:
            round_info["stopped"] = "eval_issues_remain"
            result.rounds.append(round_info)
            result.final_violations = violations_report
            result.final_evaluation = evaluation
            result.passed = False
            break

        fix_plan = plan_fixes(deck_data, violations_report, rulebook_path)
        if eval_issues and evaluation and fix_all:
            fix_plan = _merge_eval_fixes(fix_plan, evaluation, violations_report)

        round_info["fix_plan"] = fix_plan

        if not fix_plan.get("fixes"):
            # Try rebuild when planner has nothing left but violations remain.
            if content_json_path.is_file() and violation_count > 0:
                run_full_rebuild(content_json_path, ppt_path)
                round_info["actions"] = {"full_rebuild": True, "reason": "no_fixes_planned"}
                result.rounds.append(round_info)
                continue
            round_info["stopped"] = "no_fixes_planned"
            result.rounds.append(round_info)
            result.final_violations = violations_report
            result.final_evaluation = evaluation
            break

        apply_result = apply_fix_plan(
            ppt_path,
            fix_plan,
            content_json=content_json_path,
        )
        round_info["actions"] = apply_result
        result.rounds.append(round_info)

        if round_num == max_rounds:
            deck_data = extract_deck(ppt_path)
            result.final_violations = detect_deck_violations(
                deck_data,
                content_titles=content_titles,
                scope_all_slides=scope_all_slides,
            )
            if run_evaluation:
                try:
                    result.final_evaluation = evaluate_deck_format(ppt_path, rulebook_path)
                except Exception:  # noqa: BLE001
                    result.final_evaluation = evaluation
            else:
                result.final_evaluation = evaluation
            result.passed = _should_stop(
                result.final_violations,
                result.final_evaluation,
                require_eval=require_eval,
                fix_all=fix_all,
            )

    if result.final_violations is None:
        deck_data = extract_deck(ppt_path)
        result.final_violations = detect_deck_violations(
            deck_data,
            content_titles=content_titles,
            scope_all_slides=scope_all_slides,
        )
    if result.final_evaluation is None and run_evaluation:
        try:
            result.final_evaluation = evaluate_deck_format(ppt_path, rulebook_path)
        except Exception:  # noqa: BLE001
            pass
    if not result.passed:
        result.passed = _should_stop(
            result.final_violations or {"violation_count": 1},
            result.final_evaluation,
            require_eval=require_eval,
            fix_all=fix_all,
        )

    log_path = ppt_path.with_suffix(ppt_path.suffix + ".repair_log.json")
    result.repair_log_path = log_path
    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(result.to_dict(), f, indent=2, ensure_ascii=False)

    return result


def _merge_eval_fixes(
    fix_plan: dict[str, Any],
    evaluation: dict[str, Any],
    violations_report: dict[str, Any],
) -> dict[str, Any]:
    """Add fixes for eval-only issues not already in the deterministic plan."""
    import re

    existing = {
        (f.get("slide_index"), f.get("action"))
        for f in fix_plan.get("fixes", [])
    }
    fixes = list(fix_plan.get("fixes", []))

    def _service(title: str) -> str:
        base = re.sub(r"^Delivery status\s*[–-]\s*", "", title, flags=re.I)
        return re.sub(r"\s*\(Contd.*\)\s*$", "", base, flags=re.I).strip()

    det_slides = {v.get("slide_index") for v in violations_report.get("violations", [])}

    for slide in evaluation.get("slides", []):
        idx = slide.get("slide_index")
        if idx in det_slides:
            continue
        for v in slide.get("violations", []):
            rule_id = v.get("rule_id", "")
            service = _service(slide.get("title", ""))
            if rule_id == "TITLE-01" and (idx, "fix_title_en_dash") not in existing:
                fixes.append({
                    "action": "fix_title_en_dash",
                    "slide_index": idx,
                    "service_title": service,
                    "params": {},
                })
                existing.add((idx, "fix_title_en_dash"))
            elif rule_id in (
                "KA-PLC-01",
                "KA-PLC-02",
                "KA-SIZE-01",
                "GEO-02",
                "HL-UTIL-01",
                "HL-SIZE-01",
                "KA-OVERLAP-01",
            ) and (idx, "layout_repair") not in existing:
                fixes.append({
                    "action": "layout_repair",
                    "slide_index": idx,
                    "service_title": service,
                    "params": {},
                })
                existing.add((idx, "layout_repair"))
            elif rule_id == "HL-SPC-03" and (idx, "remove_extra_sprint_blanks") not in existing:
                fixes.append({
                    "action": "remove_extra_sprint_blanks",
                    "slide_index": idx,
                    "service_title": service,
                    "params": {},
                })
                existing.add((idx, "remove_extra_sprint_blanks"))

    return {**fix_plan, "fixes": fixes}
