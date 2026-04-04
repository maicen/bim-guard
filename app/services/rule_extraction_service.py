import asyncio


class RuleExtractionService:
    """Encapsulates rule extraction workflow from uploaded documents."""

    async def extract_rules(self, file_content: bytes) -> list[dict]:
        # Placeholder implementation until AI/rule-builder integration is added.
        await asyncio.sleep(1.5)
        if not file_content:
            return []

        return [
            {
                "ref": "REQ-DOC-01",
                "desc": "All files must start with Project ID",
                "target": "IfcProject",
            },
            {
                "ref": "REQ-DOC-02",
                "desc": "Columns must have LoadBearing property",
                "target": "IfcColumn",
            },
        ]
