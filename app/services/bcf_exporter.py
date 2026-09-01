"""BCF 2.1 export for compliance issues - OpenBIM standard (buildingSMART).

Exports issues to BCF Markup XML for integration with AEC review workflows.
BCF 2.1 spec: https://github.com/buildingSMART/BCF-XML
"""

import xml.etree.ElementTree as ET
from datetime import datetime
from typing import List
from uuid import uuid4

from app.modules.module4_comparator.issue_schema import Issue, RiskBand


class BCFExporter:
    """Export compliance issues as BCF 2.1 XML (Markup component)."""

    @staticmethod
    def _risk_band_to_bcf_priority(band: RiskBand) -> str:
        """Map BIMGUARD risk band to BCF priority level."""
        mapping = {
            RiskBand.CRITICAL: "Critical",
            RiskBand.HIGH: "High",
            RiskBand.MEDIUM: "Medium",
            RiskBand.LOW: "Low",
        }
        return mapping.get(band, "Medium")

    def generate_bcf_markup_xml(self, issues: List[Issue]) -> str:
        """Generate BCF Markup.bcf XML for a list of compliance issues."""
        root = ET.Element("Markup")
        root.set("xmlns", "http://www.buildingsmart-tech.org/bcf/2.1/markup")

        # BCF Header
        header = ET.SubElement(root, "Header")
        file_elem = ET.SubElement(header, "File")
        file_elem.set("IfcProject", "BIMGuard Compliance Analysis")
        file_elem.set("IfcSpatialStructureElement", "Multiple")
        ET.SubElement(file_elem, "Date").text = datetime.now().isoformat() + "Z"

        # Topics (one per issue)
        for issue in issues:
            topic = self._issue_to_bcf_topic(issue)
            root.append(topic)

        return ET.tostring(root, encoding="unicode")

    def _issue_to_bcf_topic(self, issue: Issue) -> ET.Element:
        """Convert a single Issue to a BCF Topic XML element."""
        topic = ET.Element("Topic")
        topic.set("Guid", issue.id)
        topic.set("TopicType", "Issue")
        topic.set("TopicStatus", issue.status)

        title = ET.SubElement(topic, "Title")
        title.text = issue.title or f"{issue.mechanism} - {issue.element_id[:8]}"

        description = ET.SubElement(topic, "Description")
        desc_lines = [
            f"Mechanism: {issue.mechanism}",
            f"Score: {issue.score:.2f} ({issue.band.value})",
            f"Element ID: {issue.element_id}",
            f"Rule ID: {issue.rule_id}",
        ]
        if issue.description:
            desc_lines.append(f"\n{issue.description}")
        if issue.mitigation:
            desc_lines.append(f"\nMitigation: {issue.mitigation}")
        description.text = "\n".join(desc_lines)

        created_at = issue.created_at or datetime.now().isoformat() + "Z"
        ET.SubElement(topic, "CreationDate").text = created_at
        ET.SubElement(topic, "CreationUser").text = "BIMGUARD-AI"
        ET.SubElement(topic, "ModifiedDate").text = issue.updated_at or created_at
        ET.SubElement(topic, "ModifiedUser").text = "BIMGUARD-AI"

        priority = self._risk_band_to_bcf_priority(issue.band)
        ET.SubElement(topic, "Priority").text = priority

        labels = [issue.mechanism, issue.band.value]
        if issue.metadata and isinstance(issue.metadata, dict):
            if issue.metadata.get("suitability_code"):
                labels.append(f"Suitability:{issue.metadata['suitability_code']}")
            if issue.metadata.get("cde_state"):
                labels.append(f"CDE:{issue.metadata['cde_state']}")
        for label_val in labels:
            ET.SubElement(topic, "Labels").text = label_val

        references = ET.SubElement(topic, "References")
        ref = ET.SubElement(references, "Reference")
        ref.set("ReferencedSheet", issue.element_id)
        ref.text = f"IfcElement(GlobalId={issue.element_id})"

        comments = ET.SubElement(topic, "Comments")
        comment = ET.SubElement(comments, "Comment")
        comment.set("Guid", str(uuid4()))

        ET.SubElement(comment, "Date").text = created_at
        ET.SubElement(comment, "Author").text = "BIMGUARD-AI"

        comment_text = self._format_issue_details(issue)
        ET.SubElement(comment, "Comment").text = comment_text

        comment_topic = ET.SubElement(comment, "Topic")
        comment_topic.set("Guid", issue.id)

        return topic

    def _format_issue_details(self, issue: Issue) -> str:
        """Format issue metadata as human-readable comment text."""
        lines = [
            f"Compliance Mechanism: {issue.mechanism}",
            f"Composite Score: {issue.score:.3f}",
            f"Risk Band: {issue.band.value.upper()}",
        ]

        if issue.metadata:
            lines.append("\nMechanism-Specific Data:")
            for key, value in issue.metadata.items():
                if isinstance(value, float):
                    lines.append(f"  {key}: {value:.4f}")
                else:
                    lines.append(f"  {key}: {value}")

        if issue.citations:
            lines.append("\nStandards References:")
            for citation in issue.citations:
                standard = citation.get("standard", "?")
                clause = citation.get("clause", "?")
                reason = citation.get("reason", "")
                lines.append(f"  - {standard} Clause {clause}")
                if reason:
                    lines.append(f"    Reason: {reason}")

        lines.append(f"\nAssignee Role: {issue.assignee_role}")

        return "\n".join(lines)

    def generate_bcf_zip(self, issues: List[Issue], output_path: str) -> None:
        """Generate BCF file."""
        markup_xml = self.generate_bcf_markup_xml(issues)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(markup_xml)
