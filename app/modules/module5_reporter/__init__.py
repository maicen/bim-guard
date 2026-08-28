"""
module5_reporter.py
--------------------
Generates reports from Module 4 compliance results.

Outputs:
  - CSV summary (one row per rule)
  - BCF topic dicts for failed rules (consumed by bcf_generator)
  - Visual summary dict for the web UI
"""

import csv
import io
import uuid
from datetime import UTC, date, datetime, timedelta

from app.modules.module5_reporter.bcf_generator import BCFIssue, generate_bcf

# severity -> (BCF priority, BCF status, days until due)
# Matches the Critical/Major/Normal/Minor + Active/Open/Info vocabulary the
# corrosion-engine BCF path already uses (bcf_generator.issues_from_results),
# so exported issues read consistently regardless of which BIMGuard check
# produced them.
_SEVERITY_TO_BCF = {
    "mandatory": ("Critical", "Active", 14),
    "recommended": ("Major", "Open", 30),
    "informational": ("Minor", "Info", 60),
}


class Module5_Reporter:
    """Generates compliance reports from Module 4 results."""

    # ── Public API ────────────────────────────────────────────────────────────

    def generate_csv_summary(self, compliance_results: list[dict]) -> str:
        """
        Return a CSV string — one row per rule — suitable for download.

        Columns: Rule Ref, Description, Target IFC, Property, Operator,
                 Expected, Unit, Severity, Status, Pass, Fail, Missing, Total
        """
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "Rule Ref", "Description", "Target IFC Class",
            "Property Name", "Operator", "Expected Value", "Unit",
            "Severity", "Status",
            "Pass", "Fail", "Missing", "Total Elements",
        ])
        for r in compliance_results:
            if r.get("operator") == "between":
                expected = f"{r.get('value_min')}–{r.get('value_max')}"
            else:
                expected = str(r.get("check_value") or "")
            writer.writerow([
                r.get("rule_ref",      ""),
                r.get("rule_desc",     ""),
                r.get("target",        ""),
                r.get("property_name", ""),
                r.get("operator",      ""),
                expected,
                r.get("unit",          ""),
                r.get("severity",      ""),
                r.get("status",        ""),
                r.get("pass_count",    0),
                r.get("fail_count",    0),
                r.get("missing_count", 0),
                r.get("total_count",   0),
            ])
        return output.getvalue()

    def iter_csv_summary(self, compliance_results: list[dict]):
        """Yield CSV data incrementally for streaming downloads."""
        # Reuse one in-memory row buffer and flush it per emitted CSV row.
        row_buffer = io.StringIO()
        writer = csv.writer(row_buffer)

        writer.writerow(
            [
                "Rule Ref",
                "Description",
                "Target IFC Class",
                "Property Name",
                "Operator",
                "Expected Value",
                "Unit",
                "Severity",
                "Status",
                "Pass",
                "Fail",
                "Missing",
                "Total Elements",
            ]
        )
        yield row_buffer.getvalue()
        row_buffer.seek(0)
        row_buffer.truncate(0)

        for r in compliance_results:
            if r.get("operator") == "between":
                expected = f"{r.get('value_min')}–{r.get('value_max')}"
            else:
                expected = str(r.get("check_value") or "")

            writer.writerow(
                [
                    r.get("rule_ref", ""),
                    r.get("rule_desc", ""),
                    r.get("target", ""),
                    r.get("property_name", ""),
                    r.get("operator", ""),
                    expected,
                    r.get("unit", ""),
                    r.get("severity", ""),
                    r.get("status", ""),
                    r.get("pass_count", 0),
                    r.get("fail_count", 0),
                    r.get("missing_count", 0),
                    r.get("total_count", 0),
                ]
            )
            yield row_buffer.getvalue()
            row_buffer.seek(0)
            row_buffer.truncate(0)

    def create_bcf_topic(self, failure: dict, rule: dict) -> dict:
        """
        Create a BCF-compatible topic dict for one element failure.

        Args:
            failure: one entry from compliance_result["failures"]
            rule:    the parent compliance result dict

        Returns:
            dict with guid, title, description, type, status, element_guid
        """
        return {
            "guid":         str(uuid.uuid4()),
            "title":        f"[{rule.get('rule_ref')}] {(rule.get('rule_desc') or '')[:80]}",
            "description":  (
                f"Element : {failure.get('element_name')}\n"
                f"Property: {rule.get('property_name')}\n"
                f"Issue   : {failure.get('reason')}"
            ),
            "type":         "Error" if rule.get("severity") == "mandatory" else "Warning",
            "status":       "Open",
            "priority":     rule.get("severity", "recommended"),
            "creation_date": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "element_guid": failure.get("guid"),
            # (x, y, z) mm from Module 2, or None — consumed by
            # ReportArtifactService._topic_to_issue() to give the persisted
            # BCF topic's viewpoint a real camera position, so selecting the
            # topic in the TopicsUI viewer actually flies to the element
            # instead of defaulting to the world origin.
            "position_mm":  failure.get("position_mm"),
        }

    def render_visual_report(self, compliance_results: list[dict]) -> dict:
        """
        Return a summary dict for display in the web UI dashboard / analyze page.

        Returns:
            {total_rules, passed, failed, missing_data, no_elements,
             pass_rate, mandatory_failed, by_target}
        """
        total       = len(compliance_results)
        passed      = sum(1 for r in compliance_results if r.get("status") == "PASS")
        failed      = sum(1 for r in compliance_results if r.get("status") == "FAIL")
        missing     = sum(1 for r in compliance_results if r.get("status") in ("MISSING_DATA", "PARTIAL"))
        no_elem     = sum(1 for r in compliance_results if r.get("status") == "NO_ELEMENTS")
        mand_failed = sum(
            1 for r in compliance_results
            if r.get("status") == "FAIL" and r.get("severity") == "mandatory"
        )

        by_target: dict[str, dict] = {}
        for r in compliance_results:
            t = r.get("target", "Unknown")
            if t not in by_target:
                by_target[t] = {"pass": 0, "fail": 0, "other": 0}
            s = r.get("status", "")
            if s == "PASS":
                by_target[t]["pass"] += 1
            elif s == "FAIL":
                by_target[t]["fail"] += 1
            else:
                by_target[t]["other"] += 1

        return {
            "total_rules":      total,
            "passed":           passed,
            "failed":           failed,
            "missing_data":     missing,
            "no_elements":      no_elem,
            "mandatory_failed": mand_failed,
            "pass_rate":        round(100 * passed / total, 1) if total else 0,
            "by_target":        by_target,
        }

    def bcf_topics_for_results(self, compliance_results: list[dict]) -> list[dict]:
        """Convenience: generate all BCF topics for every failure in all results."""
        topics = []
        for rule in compliance_results:
            if rule.get("status") == "FAIL":
                for failure in rule.get("failures", []):
                    topics.append(self.create_bcf_topic(failure, rule))
        return topics

    def bcf_issues_for_results(self, compliance_results: list[dict]) -> list[BCFIssue]:
        """Convert Module 4 compliance results into BCFIssue objects.

        One issue per failing element (not per rule — a rule failing on 6
        doors needs 6 separately-clickable topics in the BCF viewer, each
        pointing at its own element by GUID). Feed the result to
        bcf_generator.generate_bcf() to get the actual .bcf ZIP bytes.
        """
        issues: list[BCFIssue] = []
        for rule in compliance_results:
            if rule.get("status") != "FAIL":
                continue
            severity = str(rule.get("severity") or "mandatory")
            priority, status, due_days = _SEVERITY_TO_BCF.get(
                severity, _SEVERITY_TO_BCF["mandatory"]
            )
            due_date = (date.today() + timedelta(days=due_days)).isoformat()
            rule_ref = rule.get("rule_ref", "")
            rule_desc = rule.get("rule_desc", "")
            property_name = rule.get("property_name", "")

            for failure in rule.get("failures", []):
                element_name = failure.get("element_name") or "Component"
                # Camera and target share the element's centroid — same
                # convention as the corrosion-engine BCF path
                # (bcf_generator.issues_from_results); _viewpoint_xml then
                # offsets the camera from it so the view doesn't sit
                # exactly inside the element. None (no geometry resolved)
                # falls back to the dataclass's own origin default.
                pos = failure.get("position_mm")
                pos_kwargs = (
                    {
                        "camera_x": float(pos[0]), "camera_y": float(pos[1]), "camera_z": float(pos[2]),
                        "target_x": float(pos[0]), "target_y": float(pos[1]), "target_z": float(pos[2]),
                    }
                    if pos is not None
                    else {}
                )
                issues.append(
                    BCFIssue(
                        guid=str(uuid.uuid4()).upper(),
                        title=f"[{rule_ref}] {element_name}",
                        description=(
                            f"{rule_desc}\n\n"
                            f"Element : {element_name}\n"
                            f"Property: {property_name}\n"
                            f"Floor/room: {failure.get('storey') or '—'} / "
                            f"{failure.get('space') or '—'}\n"
                            f"Issue   : {failure.get('reason', '')}"
                        ),
                        priority=priority,
                        status=status,
                        assigned_to="",
                        due_date=due_date,
                        labels=["BIMGuard", severity, rule.get("target", "")],
                        component_guid=failure.get("guid", ""),
                        component_name=element_name,
                        service_type="",
                        floor=failure.get("storey") or "",
                        risk_band=severity.upper(),
                        mechanism="CODE",
                        risk_score=0.0,
                        mitigation="",
                        **pos_kwargs,
                    )
                )
        return issues

    def generate_bcf_zip(self, compliance_results: list[dict]) -> bytes:
        """Return a BCF 2.1 ZIP (bytes) of every failing element in compliance_results."""
        return generate_bcf(self.bcf_issues_for_results(compliance_results))
