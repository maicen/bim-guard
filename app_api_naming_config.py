# app/api/naming_config.py
# ISO 19650 Naming Configuration API Routes
# PROJ-ORG-PH-LV-TYP-RL-CL-NUM-SUIT-REV.ext

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Optional, Dict, List, Any
import json
from datetime import datetime
from app.db import get_supabase_client
from app.auth import get_current_user

router = APIRouter(prefix="/api/naming-config", tags=["naming-config"])

# ============================================================================
# Pydantic Models for Request/Response
# ============================================================================

class CodeLibraryItem(BaseModel):
    code: str
    label: str
    removable: bool

class NamingConfigRequest(BaseModel):
    """Request body for creating/updating naming configuration"""
    project_code: str = Field(..., min_length=2, max_length=8)
    originator_code: str = Field(..., min_length=2, max_length=8)
    phase_code: str = "SD"
    level_location_codes: Optional[List[CodeLibraryItem]] = None
    type_codes: Optional[List[CodeLibraryItem]] = None
    role_discipline_codes: Optional[List[CodeLibraryItem]] = None
    classification_codes: Optional[Dict[str, List[str]]] = None
    active_convention: str = "iso19650-1"
    revision_format: str = "Rev##"
    custom_format_string: Optional[str] = None

class NamingConfigResponse(BaseModel):
    """Response body for naming configuration"""
    id: str
    project_id: str
    project_code: str
    originator_code: str
    phase_code: str
    level_location_codes: List[CodeLibraryItem]
    type_codes: List[CodeLibraryItem]
    role_discipline_codes: List[CodeLibraryItem]
    classification_codes: Dict[str, List[str]]
    cde_status_mapping: Dict[str, str]
    active_convention: str
    revision_format: str
    custom_format_string: Optional[str]
    created_at: str
    updated_at: str

class NamingPreview(BaseModel):
    """Response for naming convention preview"""
    format_name: str
    description: str
    template: str
    example: str
    tokens: Dict[str, str]

# ============================================================================
# Naming Convention Presets
# ============================================================================

NAMING_PRESETS = {
    "iso19650-1": {
        "name": "ISO 19650-1:2018",
        "description": "Standard ISO naming convention (no date)",
        "template": "{project}-{originator}-{phase}-{level}-{type}-{role}-{class}-{number}-{suitability}-{revision}",
        "example": "A7000-BIM-SD-01-DR-A-A01-0001-S1-Rev01",
        "tokens": {
            "project": "Project code (2-8 chars)",
            "originator": "Originator code (2-8 chars)",
            "phase": "Phase (SD, DD, CD, etc.)",
            "level": "Level code (GF, 01, 02, ZZ, etc.)",
            "type": "Type code (DR, M3, RI, etc.)",
            "role": "Role/Discipline (A, E, H, S, etc.)",
            "class": "Classification (A01, E02, etc.)",
            "number": "Sequential number (0001-9999)",
            "suitability": "CDE status (S0, S1, S2, S3, A, B, S7)",
            "revision": "Revision code (Rev01, PV1, etc.)"
        }
    },
    "iso19650-2": {
        "name": "ISO 19650-2:2018 + Date",
        "description": "ISO naming convention with date suffix (YYYYMMDD)",
        "template": "{project}-{originator}-{phase}-{level}-{type}-{role}-{class}-{number}-{suitability}-{revision}-{date}",
        "example": "A7000-BIM-SD-01-DR-A-A01-0001-S1-Rev01-20260831",
        "tokens": {
            "project": "Project code",
            "originator": "Originator code",
            "phase": "Phase",
            "level": "Level code",
            "type": "Type code",
            "role": "Role/Discipline",
            "class": "Classification",
            "number": "Sequential number",
            "suitability": "CDE status",
            "revision": "Revision",
            "date": "YYYYMMDD date suffix"
        }
    },
    "simple": {
        "name": "Simple (Source vs Service)",
        "description": "Simplified format for smaller projects",
        "template": "{type}-{originator}-{level}-{role}-{number}",
        "example": "DR-BIM-01-A-0001",
        "tokens": {
            "type": "Type code (DR, M3, etc.)",
            "originator": "Originator",
            "level": "Level",
            "role": "Role",
            "number": "Sequential number"
        }
    },
    "descriptive": {
        "name": "Descriptive (Human-Readable)",
        "description": "Human-readable format using spaces and words",
        "template": "{originator} {type} {level} {role} {number}",
        "example": "BIM 2D Drawing Ground Floor Architecture 0001",
        "tokens": {
            "originator": "Organization name",
            "type": "Type (Drawing, Model, etc.)",
            "level": "Floor/Level name",
            "role": "Discipline name",
            "number": "Sequential number"
        }
    },
    "uniclass": {
        "name": "Uniclass 2015",
        "description": "UK Uniclass 2015 classification-based naming",
        "template": "{project}_{uniclass_code}_{level}_{number}_{revision}",
        "example": "A7000_Pr_70_01_0001_Rev01",
        "tokens": {
            "project": "Project code",
            "uniclass_code": "Uniclass code (e.g., Pr_70 for drawings)",
            "level": "Level",
            "number": "Sequential number",
            "revision": "Revision"
        }
    }
}

# ============================================================================
# API Endpoints
# ============================================================================

@router.post("/projects/{project_id}", response_model=NamingConfigResponse)
async def create_or_update_naming_config(
    project_id: str,
    config: NamingConfigRequest,
    user=Depends(get_current_user)
):
    """Create or update naming configuration for a project"""
    supabase = get_supabase_client()
    
    # Verify user owns this project
    try:
        project = supabase.table("projects").select("id, user_id").eq("id", project_id).single().execute()
        if not project.data or project.data["user_id"] != user["id"]:
            raise HTTPException(status_code=403, detail="Not authorized")
    except Exception as e:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Prepare data for database
    db_data = {
        "project_id": project_id,
        "project_code": config.project_code,
        "originator_code": config.originator_code,
        "phase_code": config.phase_code,
        "active_convention": config.active_convention,
        "revision_format": config.revision_format,
        "custom_format_string": config.custom_format_string,
    }
    
    # Convert optional lists to JSON if provided
    if config.level_location_codes:
        db_data["level_location_codes"] = [item.dict() for item in config.level_location_codes]
    if config.type_codes:
        db_data["type_codes"] = [item.dict() for item in config.type_codes]
    if config.role_discipline_codes:
        db_data["role_discipline_codes"] = [item.dict() for item in config.role_discipline_codes]
    if config.classification_codes:
        db_data["classification_codes"] = config.classification_codes
    
    try:
        # Try to update first
        result = supabase.table("project_naming_config").update(db_data).eq("project_id", project_id).execute()
        
        if not result.data:
            # If no rows updated, insert instead
            db_data["id"] = None  # Let DB generate UUID
            result = supabase.table("project_naming_config").insert(db_data).execute()
        
        if result.data:
            return result.data[0]
        else:
            raise HTTPException(status_code=500, detail="Failed to save configuration")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Database error: {str(e)}")

@router.get("/projects/{project_id}", response_model=NamingConfigResponse)
async def get_naming_config(
    project_id: str,
    user=Depends(get_current_user)
):
    """Retrieve naming configuration for a project"""
    supabase = get_supabase_client()
    
    # Verify user owns this project
    try:
        project = supabase.table("projects").select("id, user_id").eq("id", project_id).single().execute()
        if not project.data or project.data["user_id"] != user["id"]:
            raise HTTPException(status_code=403, detail="Not authorized")
    except Exception as e:
        raise HTTPException(status_code=404, detail="Project not found")
    
    try:
        result = supabase.table("project_naming_config").select("*").eq("project_id", project_id).execute()
        
        if not result.data:
            raise HTTPException(status_code=404, detail="Naming configuration not found")
        
        return result.data[0]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.get("/presets")
async def get_naming_presets():
    """Return available naming convention presets"""
    return NAMING_PRESETS

@router.post("/preview")
async def generate_naming_preview(
    project_code: str,
    originator_code: str,
    phase_code: str = "SD",
    level_code: str = "01",
    type_code: str = "DR",
    role_code: str = "A",
    class_code: str = "A01",
    number: str = "0001",
    suitability: str = "S1",
    revision: str = "Rev01",
    convention: str = "iso19650-1"
):
    """Generate preview of naming string for given parameters"""
    
    if convention not in NAMING_PRESETS:
        raise HTTPException(status_code=400, detail=f"Unknown convention: {convention}")
    
    preset = NAMING_PRESETS[convention]
    tokens = {
        "project": project_code,
        "originator": originator_code,
        "phase": phase_code,
        "level": level_code,
        "type": type_code,
        "role": role_code,
        "class": class_code,
        "number": number,
        "suitability": suitability,
        "revision": revision,
        "date": datetime.now().strftime("%Y%m%d")
    }
    
    # Format the template
    preview = preset["template"]
    for key, value in tokens.items():
        preview = preview.replace(f"{{{key}}}", value)
    
    return {
        "convention": convention,
        "template": preset["template"],
        "preview": preview,
        "tokens": tokens
    }

@router.get("/validate/{filename}")
async def validate_naming_convention(
    filename: str,
    project_id: str,
    user=Depends(get_current_user)
):
    """Validate a filename against the project's active naming convention"""
    supabase = get_supabase_client()
    
    # Get project config
    try:
        result = supabase.table("project_naming_config").select("*").eq("project_id", project_id).execute()
        if not result.data:
            raise HTTPException(status_code=404, detail="Naming config not found")
        
        config = result.data[0]
        active_convention = config.get("active_convention", "iso19650-1")
        
        # Simple validation: check if filename contains expected separators
        # This is a basic check; more sophisticated regex validation could be added
        preset = NAMING_PRESETS.get(active_convention)
        if not preset:
            raise HTTPException(status_code=400, detail="Invalid convention")
        
        # Count expected field separators
        expected_separators = preset["template"].count("-")
        actual_separators = filename.count("-")
        
        is_valid = actual_separators >= expected_separators - 1  # Allow some flexibility
        
        return {
            "filename": filename,
            "convention": active_convention,
            "is_valid": is_valid,
            "template": preset["template"],
            "message": "Filename appears compliant" if is_valid else "Filename does not match convention"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Validation error: {str(e)}")
