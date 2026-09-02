"""FastAPI router exposing the buildingSMART Data Dictionary (bSDD) integration.

Surfaces the standardized dictionaries, classes, and properties served by
``app.services.bsdd_client.BSDDClient`` as REST endpoints, so any part of the
project (project settings, the rule builder's scope fields, future scope
terminology pickers) can resolve buildingSMART-standard terms and codes
through one shared HTTP surface instead of talking to bSDD directly.
"""

from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.dependencies import get_bsdd_client
from app.logging_config import get_logger
from app.modules.contracts import (
    BSDDClassItem,
    BSDDClassSearchResponse,
    BSDDDictionaryItem,
    BSDDPropertySearchResponse,
)
from app.services.bsdd_client import BSDDClient

logger = get_logger(__name__)

router = APIRouter()


@router.get(
    "/dictionaries",
    response_model=list[BSDDDictionaryItem],
    summary="List available bSDD classification dictionaries",
)
def list_dictionaries(
    client: Annotated[BSDDClient, Depends(get_bsdd_client)],
) -> list[BSDDDictionaryItem]:
    """Return the catalog of bSDD dictionaries (IFC, Uniclass, OmniClass, ...).

    Used by project settings to let a user pick the classification standard
    a project should be coded against.
    """
    return client.list_dictionaries()


@router.get(
    "/classes/search",
    response_model=BSDDClassSearchResponse,
    summary="Search bSDD classes by text",
)
def search_classes(
    client: Annotated[BSDDClient, Depends(get_bsdd_client)],
    q: str = Query(..., min_length=1, description="Free-text search term"),
    dictionary_uri: Optional[str] = Query(default=None, description="Restrict search to one dictionary URI"),
) -> BSDDClassSearchResponse:
    """Search bSDD classes (element/classification codes) by text.

    Backs element-name autocomplete in the rule builder's scope fields.
    """
    return client.search_classes(q, dictionary_uri)


@router.get(
    "/properties/search",
    response_model=BSDDPropertySearchResponse,
    summary="Search bSDD properties by text",
)
def search_properties(
    client: Annotated[BSDDClient, Depends(get_bsdd_client)],
    q: str = Query(..., min_length=1, description="Free-text search term"),
    dictionary_uri: Optional[str] = Query(default=None, description="Restrict search to one dictionary URI"),
) -> BSDDPropertySearchResponse:
    """Search bSDD properties (property set + property name pairs) by text.

    Backs property-name autocomplete in the rule builder's scope fields.
    """
    properties = client.search_properties(q, dictionary_uri)
    return BSDDPropertySearchResponse(query=q, total=len(properties), properties=properties)


@router.get(
    "/classes/{class_code}",
    response_model=BSDDClassItem,
    summary="Get a bSDD class definition and its properties",
)
def get_class(
    class_code: str,
    client: Annotated[BSDDClient, Depends(get_bsdd_client)],
    dictionary_uri: str = Query(
        default="https://identifier.buildingsmart.org/uri/buildingsmart/ifc-4.3",
        description="Dictionary URI the class code belongs to",
    ),
) -> BSDDClassItem:
    """Fetch one bSDD class (e.g. IfcPipeSegment) with its standardized properties."""
    result = client.get_class(dictionary_uri, class_code)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"bSDD class '{class_code}' not found in dictionary '{dictionary_uri}'.",
        )
    return result


__all__ = ["router"]
