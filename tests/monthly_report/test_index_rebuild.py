from monthly_report.index_slide import IndexProject, collect_monthly_index_entries


def test_index_entries_follow_deck_order_and_dedupe():
    projects = [
        IndexProject("Pricing Core", 4),
        IndexProject("Cost Core Service", 2),
        IndexProject("Pricing Core", 4),
        IndexProject("GSS", 6),
    ]
    labels = {
        "Pricing Core": "Pricing Core",
        "Cost Core Service": "Cost Core Service",
        "GSS": "Global Sourcing Solution",
    }
    entries = collect_monthly_index_entries(projects, labels)
    assert entries == [
        (2, "Cost Core Service"),
        (4, "Pricing Core"),
        (6, "Global Sourcing Solution"),
    ]
    slide_numbers = [slide + 1 for slide, _ in entries]
    assert slide_numbers == sorted(slide_numbers)
