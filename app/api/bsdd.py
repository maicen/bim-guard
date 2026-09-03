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

from app.api.dependencies import get_bsdd_client, get_bsdd_ontology
from app.modules.contracts import (
    BSDDClassItem,
    BSDDClassSearchResponse,
    BSDDDictionaryItem,
    BSDDPropertySearchResponse,
)
from app.services.bsdd_client import BSDDClient
from app.services.bsdd_ontology_repository import BSDDOntologyRepository

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
    ontology: Annotated[BSDDOntologyRepository, Depends(get_bsdd_ontology)],
    q: str = Query(..., min_length=1, description="Free-text search term"),
    dictionary_uri: Optional[str] = Query(default=None, description="Restrict search to one dictionary URI"),
) -> BSDDClassSearchResponse:
    """Search bSDD classes (element/classification codes) by text.

    Backs element-name autocomplete in the rule builder's scope fields.
    Checks the local ontology cache first -- instant, no live bSDD call --
    and only reaches the live API when nothing local matches.
    """
    local = ontology.search_classes(q)
    if local:
        return BSDDClassSearchResponse(query=q, total=len(local), classes=local)
    return client.search_classes(q, dictionary_uri)


@router.get(
    "/properties/search",
    response_model=BSDDPropertySearchResponse,
    summary="Search bSDD properties by text",
)
def search_properties(
    client: Annotated[BSDDClient, Depends(get_bsdd_client)],
    ontology: Annotated[BSDDOntologyRepository, Depends(get_bsdd_ontology)],
    q: str = Query(..., min_length=1, description="Free-text search term"),
    dictionary_uri: Optional[str] = Query(default=None, description="Restrict search to one dictionary URI"),
) -> BSDDPropertySearchResponse:
    """Search bSDD properties (property set + property name pairs) by text.

    Backs property-name autocomplete in the rule builder's scope fields.
    Checks the local ontology cache first -- instant, no live bSDD call --
    and only reaches the live API when nothing local matches.
    """
    local = ontology.search_properties(q)
    if local:
        return BSDDPropertySearchResponse(query=q, total=len(local), properties=local)
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
    ontology: Annotated[BSDDOntologyRepository, Depends(get_bsdd_ontology)],
    dictionary_uri: str = Query(
        # The real buildingSMART IFC 4.3 dictionary URI uses a slash, not a
        # hyphen, before the version (identifier.buildingsmart.org/.../ifc/4.3)
        # -- live bSDD tolerates either form, but this app's local ontology
        # cache (see scripts/crawl_bsdd_ontology.py) is keyed by the real
        # slash URI, so the hyphenated default here always missed the cache
        # and paid for a live round trip on every single lookup.
        default="https://identifier.buildingsmart.org/uri/buildingsmart/ifc/4.3",
        description="Dictionary URI the class code belongs to",
    ),
) -> BSDDClassItem:
    """Fetch one bSDD class (e.g. IfcPipeSegment) with its standardized properties.

    Local ontology first; a miss falls through to a live bSDD lookup, whose
    result is then cached locally so the next call for this class is local.
    """
    result = ontology.get_class_cached(client, dictionary_uri, class_code)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"bSDD class '{class_code}' not found in dictionary '{dictionary_uri}'.",
        )
    return result


@router.get(
    "/ontology/classes",
    summary="List every class in the local bSDD ontology cache",
)
def list_ontology_classes(
    ontology: Annotated[BSDDOntologyRepository, Depends(get_bsdd_ontology)],
) -> list[dict]:
    """Lightweight rows (uri/code/name/parent) for browsing -- backs the bSDD wiki's class tree."""
    return ontology.list_classes()


@router.get(
    "/ontology/class",
    response_model=BSDDClassItem,
    summary="Full detail for one class in the local ontology, by URI",
)
def get_ontology_class(
    ontology: Annotated[BSDDOntologyRepository, Depends(get_bsdd_ontology)],
    uri: str = Query(..., description="Full bSDD class URI"),
) -> BSDDClassItem:
    result = ontology.get_class_by_uri(uri)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"'{uri}' is not in the local ontology cache.")
    return result


@router.get(
    "/ontology/property",
    summary="Full detail for one property in the local ontology, by URI, plus which classes use it",
)
def get_ontology_property(
    ontology: Annotated[BSDDOntologyRepository, Depends(get_bsdd_ontology)],
    uri: str = Query(..., description="Full bSDD property URI"),
) -> dict:
    result = ontology.get_property_by_uri(uri)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"'{uri}' is not in the local ontology cache.")
    return result


__all__ = ["router"]
