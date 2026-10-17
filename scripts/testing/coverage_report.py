"""Render owned certification coverage and enforce its exact combined threshold."""

import json
import sys
from pathlib import Path
from xml.etree import ElementTree

import coverage


def evaluate(report):
    """Use coverage.py's statement/branch counts without percentage rounding."""
    if not report["meta"]["branch_coverage"]:
        raise ValueError("Branch coverage is required")
    totals = report["totals"]
    statements = totals["num_statements"]
    branches = totals["num_branches"]
    covered_lines = totals["covered_lines"]
    covered_branches = totals["covered_branches"]
    if statements <= 0 or branches <= 0:
        raise ValueError("Empty statement or branch coverage measurement")
    if not (0 <= covered_lines <= statements and 0 <= covered_branches <= branches):
        raise ValueError("Invalid coverage counts")
    if (
        totals["missing_lines"] != statements - covered_lines
        or totals["missing_branches"] != branches - covered_branches
    ):
        raise ValueError("Inconsistent missing coverage counts")
    covered, total = covered_lines + covered_branches, statements + branches
    print(
        f"Statement coverage: {100 * covered_lines / statements:.6f}% "
        f"({totals['missing_lines']} missing statements)"
    )
    print(
        f"Branch coverage: {100 * covered_branches / branches:.6f}% "
        f"({totals['missing_branches']} missing branches)"
    )
    print(f"Combined coverage: {100 * covered / total:.6f}% ({covered}/{total}); required: 95%")
    return 100 * covered >= 95 * total


def main(directory):
    """Reports survive even when the coverage gate fails; this never certifies tests."""
    directory = Path(directory)
    cov = coverage.Coverage(config_file=".coveragerc")
    if cov.get_option("report:fail_under") != 95 or not cov.get_option("run:branch"):
        raise ValueError("Certification requires branch coverage and fail_under = 95")
    cov.load()
    cov.report(show_missing=True)
    cov.json_report(outfile=str(directory / "coverage.json"))
    cov.xml_report(outfile=str(directory / "coverage.xml"))
    report = json.loads((directory / "coverage.json").read_text())
    if ElementTree.parse(directory / "coverage.xml").getroot().tag != "coverage":
        raise ValueError("Invalid coverage XML report")
    passed = evaluate(report)
    print("Coverage gate: " + ("PASS" if passed else "FAIL (below 95%)"))
    return 0 if passed else 2


if __name__ == "__main__":
    try:
        if len(sys.argv) != 2:
            raise ValueError("An owned report directory is required")
        sys.exit(main(sys.argv[1]))
    except (OSError, ValueError, KeyError, coverage.CoverageException) as exc:
        sys.exit(f"Coverage reporting failed: {exc}")
