"""Shared dataclasses for the WSR engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

SlideType = Literal[
    "PROJECT_MAIN",
    "PROJECT_KA",
    "PROJECT_CONTINUATION",
    "INDEX",
    "COVER",
    "OTHER",
]


@dataclass
class SlideDescriptor:
    index: int
    title: str
    slide_type: SlideType
    project_name: str | None = None
    has_highlights: bool = False
    has_ka: bool = False


@dataclass
class ProjectMap:
    project_name: str
    main_slide_index: int
    continuation_indices: list[int] = field(default_factory=list)
    ka_slide_index: int | None = None

    @property
    def all_slide_indices(self) -> list[int]:
        indices = [self.main_slide_index, *self.continuation_indices]
        if self.ka_slide_index is not None and self.ka_slide_index not in indices:
            indices.append(self.ka_slide_index)
        return sorted(set(indices))


@dataclass
class SprintSection:
    sprint_name: str
    sprint_dates: str
    sprint_status: str
    completed: list[str]
    released: list[str]
    inprogress: list[str]
    continued_section: bool = False
    omit_category_headers: list[str] = field(default_factory=list)

    def to_display_dict(self) -> dict[str, Any]:
        total = len(self.completed) + len(self.released) + len(self.inprogress)
        return {
            "sprint_bold": f"Sprint \u2013 {self.sprint_name}, {self.sprint_status} ",
            "sprint_light": (
                f"({self.sprint_dates}) Stories (Total \u2013 {total}, "
                f"Done \u2013 {len(self.completed)}, In-review \u2013 {len(self.released)}, "
                f"In-progress \u2013 {len(self.inprogress)})"
            ),
            "completed_count": str(len(self.completed)),
            "completed_items": self.completed,
            "released_count": str(len(self.released)),
            "released_items": self.released,
            "inprogress_count": str(len(self.inprogress)),
            "inprogress_items": self.inprogress,
            "continued_section": self.continued_section,
            "omit_category_headers": list(self.omit_category_headers),
        }


@dataclass
class ProjectContent:
    title: str
    project_key: str = ""
    project_name: str = ""
    sections: list[SprintSection] = field(default_factory=list)
    key_activities: list[str] = field(default_factory=list)


@dataclass
class WsrContent:
    report_start_date: str
    report_end_date: str
    projects: list[ProjectContent] = field(default_factory=list)


@dataclass
class OverflowPlan:
    main_sections: list[dict[str, Any]]
    continuation_chains: list[list[dict[str, Any]]]
    ka_on_main: bool = False
    ka_contd_only: bool = False


@dataclass
class TitleFormat:
    prefix: str
    separator: str
    contd_marker: str


@dataclass
class TemplateModel:
    template_path: str
    slides: list[SlideDescriptor] = field(default_factory=list)
    projects: list[ProjectMap] = field(default_factory=list)
    index_slide_index: int | None = None
    title_format: TitleFormat | None = None
    profile: Any = None

    def project_by_name(self, name: str) -> ProjectMap | None:
        needle = name.strip().lower()
        for proj in self.projects:
            if proj.project_name.lower() == needle:
                return proj
            if needle in proj.project_name.lower() or proj.project_name.lower() in needle:
                return proj
        return None


@dataclass
class BuildReport:
    detected_projects: int = 0
    matched_projects: int = 0
    deleted_projects: int = 0
    inserted_projects: list[str] = field(default_factory=list)
    continuations_created: int = 0
    index_entries_updated: int = 0
    output_path: str = ""
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def summary_lines(self) -> list[str]:
        lines = [
            f"Detected {self.detected_projects} projects",
            f"Matched {self.matched_projects} projects",
            f"Deleted {self.deleted_projects} projects",
        ]
        if self.inserted_projects:
            lines.append(f"Inserted: {', '.join(self.inserted_projects)}")
        if self.continuations_created:
            lines.append(f"Created {self.continuations_created} continuation slide(s)")
        if self.index_entries_updated:
            lines.append(f"Updated {self.index_entries_updated} index entries")
        if self.output_path:
            lines.append(f"Saved: {self.output_path}")
        for w in self.warnings:
            lines.append(f"Warning: {w}")
        for e in self.errors:
            lines.append(f"Error: {e}")
        return lines
