"""ISO 19650-2 National Annex File Naming Validator."""

import re
from pathlib import Path
from typing import Dict, Optional


class ISO19650ValidationError(ValueError):
    """Exception raised for ISO 19650 naming convention violations."""
    pass


def validate_and_parse_filename(
    filename: str, 
    separator: str = "-", 
    expected_project_code: Optional[str] = None
) -> Dict[str, str]:
    """
    Validate and parse a filename according to the ISO 19650-2 7-field convention.
    
    Format: Project-Originator-VolumeSystem-Level-Type-Role-Number.ext
    
    Args:
        filename: The uploaded filename.
        separator: The field delimiter (default is '-').
        expected_project_code: If provided, Field 1 must exactly match this.
        
    Returns:
        A dictionary mapping the 7 fields to their parsed values.
        
    Raises:
        ISO19650ValidationError: If the filename violates the naming standards.
    """
    path = Path(filename)
    stem = path.stem
    extension = path.suffix

    if not extension:
        raise ISO19650ValidationError(f"File '{filename}' must have an extension.")
    
    # ISO 19650 forbids spaces, underscores (if '-' is separator), and other symbols in values.
    # The stem must only contain alphanumeric characters and the exact separator.
    if " " in stem:
        raise ISO19650ValidationError(f"File '{filename}' contains invalid spaces.")

    fields = stem.split(separator)
    
    if len(fields) != 7:
        raise ISO19650ValidationError(
            f"File '{filename}' must contain exactly 7 fields separated by '{separator}'. Found {len(fields)}."
        )

    project_code, originator, volume_system, level, type_code, role, number = fields

    # Field 1: Project (2-6 Alphanumeric)
    if not re.match(r"^[A-Za-z0-9]{2,6}$", project_code):
        raise ISO19650ValidationError(f"Project code '{project_code}' must be 2-6 alphanumeric characters.")
    
    if expected_project_code and project_code != expected_project_code:
        raise ISO19650ValidationError(
            f"Project code '{project_code}' does not match the expected project '{expected_project_code}'."
        )

    # Field 2: Originator (3-6 Alphanumeric)
    if not re.match(r"^[A-Za-z0-9]{3,6}$", originator):
        raise ISO19650ValidationError(f"Originator code '{originator}' must be 3-6 alphanumeric characters.")

    # Field 3: Volume/System (2 Alphanumeric)
    if not re.match(r"^[A-Za-z0-9]{2}$", volume_system):
        raise ISO19650ValidationError(f"Volume/System code '{volume_system}' must be exactly 2 alphanumeric characters.")

    # Field 4: Level (2 Alphanumeric)
    if not re.match(r"^[A-Za-z0-9]{2}$", level):
        raise ISO19650ValidationError(f"Level code '{level}' must be exactly 2 alphanumeric characters.")

    # Field 5: Type (2 Alphabetic)
    if not re.match(r"^[A-Za-z]{2}$", type_code):
        raise ISO19650ValidationError(f"Type code '{type_code}' must be exactly 2 alphabetic characters.")

    # Field 6: Role/Discipline (1-2 Alphabetic)
    if not re.match(r"^[A-Za-z]{1,2}$", role):
        raise ISO19650ValidationError(f"Role code '{role}' must be 1-2 alphabetic characters.")

    # Field 7: Number (4-6 Numeric)
    if not re.match(r"^[0-9]{4,6}$", number):
        raise ISO19650ValidationError(f"Number '{number}' must be 4-6 numeric characters.")

    return {
        "project_code": project_code,
        "originator": originator,
        "volume_system": volume_system,
        "level": level,
        "type": type_code,
        "role": role,
        "number": number,
    }
