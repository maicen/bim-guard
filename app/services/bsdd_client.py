"""buildingSMART Data Dictionary (bSDD) Client & Semantic Validation Service.

Standard: ISO 12006-3 / buildingSMART bSDD REST API v1
Official API: https://api.bsdd.buildingsmart.org
Test API: https://test.bsdd.buildingsmart.org
"""

from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from typing import Any, Optional

from cachetools import TTLCache

from app.logging_config import get_logger
from app.modules.contracts import (
    BSDDClassItem,
    BSDDClassSearchResponse,
    BSDDDictionaryItem,
    BSDDPropertyItem,
    BSDDValidationResult,
    BSDDValidationViolation,
)

logger = get_logger(__name__)

DEFAULT_BSDD_BASE_URL = os.getenv("BSDD_API_BASE_URL", "https://api.bsdd.buildingsmart.org")
FALLBACK_BSDD_BASE_URL = "https://test.bsdd.buildingsmart.org"

# ------------------------------------------------------------------------------
# Built-in Resilient Fallback Dictionaries (for offline & air-gapped operations)
# ------------------------------------------------------------------------------

FALLBACK_DICTIONARIES: list[dict[str, Any]] = [
    {
        "uri": "https://identifier.buildingsmart.org/uri/buildingsmart/ifc-4.3",
        "code": "ifc_4.3",
        "name": "buildingSMART IFC 4.3 Standard Property and Classification Dictionary",
        "version": "4.3.0",
        "organization_code_owner": "buildingSMART",
        "language_iso_code": "en-GB",
        "classes_count": 8,
    },
    {
        "uri": "https://identifier.buildingsmart.org/uri/bs-ag/uniclass-2015",
        "code": "uniclass_2015",
        "name": "Uniclass 2015 Classification System",
        "version": "2024.1",
        "organization_code_owner": "NBS",
        "language_iso_code": "en-GB",
        "classes_count": 5,
    },
    {
        "uri": "https://identifier.buildingsmart.org/uri/omniclass/omniclass-2020",
        "code": "omniclass_2020",
        "name": "OmniClass Construction Classification System",
        "version": "2020",
        "organization_code_owner": "CSI",
        "language_iso_code": "en-US",
        "classes_count": 4,
    },
]

FALLBACK_CLASSES: dict[str, dict[str, Any]] = {
    "IfcPipeSegment": {
        "uri": "https://identifier.buildingsmart.org/uri/buildingsmart/ifc-4.3/class/IfcPipeSegment",
        "code": "IfcPipeSegment",
        "name": "Pipe Segment",
        "dictionary_uri": "https://identifier.buildingsmart.org/uri/buildingsmart/ifc-4.3",
        "related_ifc_entities": ["IfcPipeSegment", "IfcFlowSegment"],
        "description": "A segment of pipe used to convey fluids.",
        "properties": [
            {
                "uri": "https://identifier.buildingsmart.org/uri/buildingsmart/ifc-4.3/prop/NominalDiameter",
                "name": "NominalDiameter",
                "property_set": "Pset_PipeSegmentCommon",
                "data_type": "IfcLengthMeasure",
                "units": "mm",
                "allowed_values": [],
                "description": "Nominal diameter of the pipe segment.",
            },
            {
                "uri": "https://identifier.buildingsmart.org/uri/buildingsmart/ifc-4.3/prop/CorrosionAllowance",
                "name": "CorrosionAllowance",
                "property_set": "Pset_PipeSegmentCommon",
                "data_type": "IfcLengthMeasure",
                "units": "mm",
                "allowed_values": [],
                "description": "Corrosion allowance thickness.",
            },
            {
                "uri": "https://identifier.buildingsmart.org/uri/buildingsmart/ifc-4.3/prop/Material",
                "name": "Material",
                "property_set": "Pset_PipeSegmentCommon",
                "data_type": "IfcLabel",
                "units": None,
                "allowed_values": [
                    "Carbon Steel",
                    "Stainless Steel 316",
                    "Stainless Steel 304",
                    "Copper",
                    "Galvanized Steel",
                    "Duplex Stainless Steel",
                    "PVC",
                    "HDPE",
                ],
                "description": "Material classification.",
            },
            {
                "uri": "https://identifier.buildingsmart.org/uri/buildingsmart/ifc-4.3/prop/PressureRating",
                "name": "PressureRating",
                "property_set": "Pset_PipeSegmentCommon",
                "data_type": "IfcPressureMeasure",
                "units": "bar",
                "allowed_values": ["PN6", "PN10", "PN16", "PN25", "PN40", "PN64", "PN100"],
                "description": "Pressure class rating.",
            },
        ],
    },
    "IfcValve": {
        "uri": "https://identifier.buildingsmart.org/uri/buildingsmart/ifc-4.3/class/IfcValve",
        "code": "IfcValve",
        "name": "Valve",
        "dictionary_uri": "https://identifier.buildingsmart.org/uri/buildingsmart/ifc-4.3",
        "related_ifc_entities": ["IfcValve", "IfcFlowController"],
        "description": "A valve used to control or isolate fluid flow.",
        "properties": [
            {
                "uri": "https://identifier.buildingsmart.org/uri/buildingsmart/ifc-4.3/prop/ValveType",
                "name": "ValveType",
                "property_set": "Pset_ValveTypeCommon",
                "data_type": "IfcLabel",
                "units": None,
                "allowed_values": ["BALL", "BUTTERFLY", "CHECK", "GATE", "GLOBE", "PLUG", "SAFETY"],
                "description": "Type of valve mechanism.",
            },
            {
                "uri": "https://identifier.buildingsmart.org/uri/buildingsmart/ifc-4.3/prop/Material",
                "name": "Material",
                "property_set": "Pset_ValveTypeCommon",
                "data_type": "IfcLabel",
                "units": None,
                "allowed_values": ["Bronze", "Cast Iron", "Ductile Iron", "Stainless Steel 316", "Carbon Steel"],
                "description": "Body material.",
            },
        ],
    },
    "IfcPump": {
        "uri": "https://identifier.buildingsmart.org/uri/buildingsmart/ifc-4.3/class/IfcPump",
        "code": "IfcPump",
        "name": "Pump",
        "dictionary_uri": "https://identifier.buildingsmart.org/uri/buildingsmart/ifc-4.3",
        "related_ifc_entities": ["IfcPump", "IfcFlowMovingDevice"],
        "description": "Mechanical device used to move fluids.",
        "properties": [
            {
                "uri": "https://identifier.buildingsmart.org/uri/buildingsmart/ifc-4.3/prop/PumpType",
                "name": "PumpType",
                "property_set": "Pset_PumpTypeCommon",
                "data_type": "IfcLabel",
                "units": None,
                "allowed_values": ["CENTRIFUGAL", "POSITIVE_DISPLACEMENT", "RECIPROCATING", "ROTARY"],
                "description": "Pump mechanism category.",
            }
        ],
    },
    "Pr_65_52_63": {
        "uri": "https://identifier.buildingsmart.org/uri/bs-ag/uniclass-2015/class/Pr_65_52_63",
        "code": "Pr_65_52_63",
        "name": "Pipe and tube products",
        "dictionary_uri": "https://identifier.buildingsmart.org/uri/bs-ag/uniclass-2015",
        "related_ifc_entities": ["IfcPipeSegment", "IfcFlowSegment"],
        "description": "Uniclass 2015 product code for pipes and tubes.",
        "properties": [],
    },
    "Pr_65_54_97": {
        "uri": "https://identifier.buildingsmart.org/uri/bs-ag/uniclass-2015/class/Pr_65_54_97",
        "code": "Pr_65_54_97",
        "name": "Valves and control products",
        "dictionary_uri": "https://identifier.buildingsmart.org/uri/bs-ag/uniclass-2015",
        "related_ifc_entities": ["IfcValve"],
        "description": "Uniclass 2015 product code for valves.",
        "properties": [],
    },
    "23-33 00 00": {
        "uri": "https://identifier.buildingsmart.org/uri/omniclass/omniclass-2020/class/23-33_00_00",
        "code": "23-33 00 00",
        "name": "Plumbing and Piping",
        "dictionary_uri": "https://identifier.buildingsmart.org/uri/omniclass/omniclass-2020",
        "related_ifc_entities": ["IfcPipeSegment", "IfcPipeFitting", "IfcValve"],
        "description": "OmniClass Table 23 - Plumbing and Piping.",
        "properties": [],
    },
}


class BSDDClient:
    """Centralized client for buildingSMART Data Dictionary REST API."""

    def __init__(
        self,
        base_url: str = DEFAULT_BSDD_BASE_URL,
        timeout_seconds: float = 3.0,
        enable_network: bool = True,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.enable_network = enable_network
        # LRU cache keeping up to 500 items for 1 hour
        self._cache: TTLCache[str, Any] = TTLCache(maxsize=500, ttl=3600)

    def _http_get(self, endpoint: str, params: dict[str, str] | None = None) -> dict[str, Any] | None:
        """Perform HTTP GET request with caching and fallback error handling."""
        query_str = f"?{urllib.parse.urlencode(params)}" if params else ""
        url = f"{self.base_url}{endpoint}{query_str}"
        cache_key = f"GET:{url}"

        if cache_key in self._cache:
            return self._cache[cache_key]

        if not self.enable_network:
            return None

        try:
            req = urllib.request.Request(
                url,
                headers={
                    "Accept": "application/json",
                    "User-Agent": "BIMGuard-AI/1.0 (buildingSMART-Integration)",
                },
            )
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as response:
                if response.status == 200:
                    data = json.loads(response.read().decode("utf-8"))
                    self._cache[cache_key] = data
                    return data
        except Exception as exc:
            logger.debug("bSDD HTTP request failed for %s: %s", url, exc)

        return None

    def list_dictionaries(self) -> list[BSDDDictionaryItem]:
        """Fetch list of available dictionaries from bSDD or offline catalog."""
        api_data = self._http_get("/api/Dictionary/v1")
        if api_data and isinstance(api_data, list):
            res = []
            for item in api_data:
                res.append(
                    BSDDDictionaryItem(
                        uri=item.get("uri", ""),
                        code=item.get("code", ""),
                        name=item.get("name", ""),
                        version=item.get("version", "1.0"),
                        organization_code_owner=item.get("organizationCodeOwner", "buildingSMART"),
                        language_iso_code=item.get("languageIsoCode", "en-GB"),
                        classes_count=item.get("classesCount", 0),
                    )
                )
            return res

        # Fallback catalog
        return [BSDDDictionaryItem(**d) for d in FALLBACK_DICTIONARIES]

    def get_class(self, dictionary_uri: str, class_code: str) -> Optional[BSDDClassItem]:
        """Fetch class definition and properties from bSDD by dictionary URI and class code."""
        cache_key = f"class:{dictionary_uri}:{class_code}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        # Try API
        api_data = self._http_get("/api/Class/v1", {"dictionaryUri": dictionary_uri, "code": class_code})

        if api_data and isinstance(api_data, dict) and "code" in api_data:
            props = []
            for p in api_data.get("properties", []):
                props.append(
                    BSDDPropertyItem(
                        uri=p.get("uri", ""),
                        name=p.get("name", ""),
                        property_set=p.get("propertySet"),
                        data_type=p.get("dataType"),
                        units=p.get("units"),
                        allowed_values=p.get("allowedValues", []),
                        description=p.get("description"),
                    )
                )
            class_item = BSDDClassItem(
                uri=api_data.get("uri", f"{dictionary_uri}/class/{class_code}"),
                code=api_data.get("code", class_code),
                name=api_data.get("name", class_code),
                dictionary_uri=dictionary_uri,
                parent_class_code=api_data.get("parentClassCode"),
                related_ifc_entities=api_data.get("relatedIfcEntities", []),
                properties=props,
                description=api_data.get("description"),
            )
            self._cache[cache_key] = class_item
            return class_item

        # Fallback offline dictionary
        if class_code in FALLBACK_CLASSES:
            raw = FALLBACK_CLASSES[class_code]
            props = [BSDDPropertyItem(**p) for p in raw.get("properties", [])]
            class_item = BSDDClassItem(
                uri=raw["uri"],
                code=raw["code"],
                name=raw["name"],
                dictionary_uri=raw["dictionary_uri"],
                related_ifc_entities=raw.get("related_ifc_entities", []),
                properties=props,
                description=raw.get("description"),
            )
            self._cache[cache_key] = class_item
            return class_item

        return None

    def search_classes(self, query: str, dictionary_uri: str | None = None) -> BSDDClassSearchResponse:
        """Search bSDD classes matching a text query."""
        params = {"search": query}
        if dictionary_uri:
            params["dictionaryUri"] = dictionary_uri

        api_data = self._http_get("/api/TextSearch/v1", params)
        if api_data and isinstance(api_data, dict) and "classes" in api_data:
            results = []
            for c in api_data.get("classes", []):
                results.append(
                    BSDDClassItem(
                        uri=c.get("uri", ""),
                        code=c.get("code", ""),
                        name=c.get("name", ""),
                        dictionary_uri=c.get("dictionaryUri", dictionary_uri or ""),
                        description=c.get("description"),
                    )
                )
            return BSDDClassSearchResponse(query=query, total=len(results), classes=results)

        # Fallback search
        lowered = query.lower()
        matched = []
        for code, raw in FALLBACK_CLASSES.items():
            if lowered in code.lower() or lowered in raw.get("name", "").lower() or lowered in raw.get("description", "").lower():
                props = [BSDDPropertyItem(**p) for p in raw.get("properties", [])]
                matched.append(
                    BSDDClassItem(
                        uri=raw["uri"],
                        code=raw["code"],
                        name=raw["name"],
                        dictionary_uri=raw["dictionary_uri"],
                        related_ifc_entities=raw.get("related_ifc_entities", []),
                        properties=props,
                        description=raw.get("description"),
                    )
                )

        return BSDDClassSearchResponse(query=query, total=len(matched), classes=matched)

    def validate_element_semantics(
        self,
        element: dict[str, Any] | Any,
        dictionary_uri: str = "https://identifier.buildingsmart.org/uri/buildingsmart/ifc-4.3",
    ) -> BSDDValidationResult:
        """Validate element property sets, properties, and material definitions against bSDD dictionary schema."""
        guid = str(
            getattr(element, "GlobalId", None)
            or (element.get("GlobalId") if isinstance(element, dict) else None)
            or getattr(element, "global_id", None)
            or (element.get("guid") if isinstance(element, dict) else None)
            or "UNKNOWN-GUID"
        )
        element_type = str(
            getattr(element, "is_a", lambda: getattr(element, "element_type", ""))()
            or (element.get("element_type") if isinstance(element, dict) else None)
            or "IfcPipeSegment"
        )

        info = getattr(element, "get_info", lambda: {})() if hasattr(element, "get_info") else (element if isinstance(element, dict) else {})
        if not isinstance(info, dict):
            info = {}

        bsdd_class = self.get_class(dictionary_uri, element_type)
        if not bsdd_class:
            # Try generic IFC fallback
            bsdd_class = self.get_class("https://identifier.buildingsmart.org/uri/buildingsmart/ifc-4.3", element_type)

        violations: list[BSDDValidationViolation] = []
        total_checks = 0
        passed_checks = 0

        if not bsdd_class:
            return BSDDValidationResult(
                passed=True,
                dictionary_uri=dictionary_uri,
                total_elements_checked=1,
                total_properties_checked=0,
                passed_count=0,
                violations_count=0,
                compliance_score_pct=100.0,
                violations=[],
            )

        # Check required/standard properties and allowed values
        for prop in bsdd_class.properties:
            total_checks += 1
            prop_name = prop.name
            pset_name = prop.property_set

            val = None
            if prop_name in info:
                val = info[prop_name]
            elif pset_name and isinstance(info.get("psets"), dict) and pset_name in info["psets"]:
                val = info["psets"][pset_name].get(prop_name)
            elif hasattr(element, prop_name):
                val = getattr(element, prop_name)

            if val is None:
                # Missing property warning
                violations.append(
                    BSDDValidationViolation(
                        element_guid=guid,
                        element_type=element_type,
                        field_checked=f"{pset_name or 'Default'}.{prop_name}",
                        expected_constraint=f"Defined property with type {prop.data_type or 'Any'}",
                        actual_value=None,
                        severity="warning",
                        message=f"Element {guid} missing recommended bSDD property '{prop_name}' ({prop.description or ''})",
                        dictionary_uri=dictionary_uri,
                    )
                )
            else:
                # Value is present, check allowed values constraint
                if prop.allowed_values and len(prop.allowed_values) > 0:
                    str_val = str(val).strip()
                    allowed_lower = [v.lower() for v in prop.allowed_values]
                    if str_val.lower() not in allowed_lower and not any(str_val.lower() in v.lower() for v in prop.allowed_values):
                        violations.append(
                            BSDDValidationViolation(
                                element_guid=guid,
                                element_type=element_type,
                                field_checked=f"{pset_name or 'Default'}.{prop_name}",
                                expected_constraint=f"One of: {', '.join(prop.allowed_values)}",
                                actual_value=str_val,
                                severity="error",
                                message=f"Element {guid} value '{str_val}' for '{prop_name}' violates bSDD allowed enumeration.",
                                dictionary_uri=dictionary_uri,
                            )
                        )
                    else:
                        passed_checks += 1
                else:
                    passed_checks += 1

        score = 100.0 if total_checks == 0 else round((passed_checks / total_checks) * 100.0, 2)
        has_errors = any(v.severity == "error" for v in violations)

        return BSDDValidationResult(
            passed=not has_errors,
            dictionary_uri=dictionary_uri,
            total_elements_checked=1,
            total_properties_checked=total_checks,
            passed_count=passed_checks,
            violations_count=len(violations),
            compliance_score_pct=score,
            violations=violations,
        )


# Global Singleton Client Instance
DEFAULT_BSDD_CLIENT = BSDDClient()
