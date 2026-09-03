"""Authoritative evaluation policy: template is ground truth.

EXPECTED = value or behavior observed in the original template slide/layout.
ACTUAL  = value or behavior observed in the generated slide.

The evaluator compares ACTUAL against EXPECTED for every applicable property
(font, size, weight, color, spacing, bullets, alignment, HL/KA tab geometry,
margins, proportions, hierarchy). Report only meaningful deviations.

Paragraph role labels and anchor text (e.g. current-week status line, category
headers) come from ``template_label_spec.extract_template_label_spec()``.

Typography expectations (font, size, weight, color, line spacing, space-before)
come from ``template_typography.extract_template_typography()``.

Layout inch bands (HL/KA waste, footer clearance, HL–KA gap) come from
``template_calibration.calibrate_from_deck()`` on the same reference template.

HL/KA prototype geometry comes from ``template_layout_spec`` and is compared
via ``template_layout_compare.detect_template_layout_deviations()``.

Do not substitute generic PowerPoint rules or universal inch/pt constants when
the template provides the reference.

Container waste (HL/KA top/bottom slack, continuation box height) is only
reported in validation when empty space exceeds BOTH the template-calibrated
band and ``CONTAINER_WASTE_REPORT_MIN_IN``. Smaller intentional slack passes
silently.
"""

# Minimum empty space (inches) before HL/KA container waste appears in reports.
# Template-calibrated limits still apply above this floor.
CONTAINER_WASTE_REPORT_MIN_IN = 2.0
