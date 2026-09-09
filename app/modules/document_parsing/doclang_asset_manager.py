"""DocLang Multimodal Asset Manager.

Extracts inline base64 images and figures from DocLang XML, offloading them
to persistent object storage (sb://.../doclang/{id}/assets/...) and replacing
bulky inline data URIs with canonical asset references.
"""

from __future__ import annotations

import base64
import re
from typing import TYPE_CHECKING

from app.logging_config import get_logger

if TYPE_CHECKING:
    from app.services.object_storage import ObjectStorage

logger = get_logger(__name__)

# Matches data:image/<ext>;base64,<encoded_data>
DATA_URI_PATTERN = re.compile(
    r'src=[\'"]data:image/(?P<ext>[a-zA-Z0-9\+\-]+);base64,(?P<data>[A-Za-z0-9+/=\s]+)[\'"]'
)


class DocLangAssetManager:
    """Manages offloading and packaging of multimodal assets embedded in DocLang XML."""

    @staticmethod
    def extract_and_offload_assets(
        doclang_xml: str,
        doc_key: str,
        storage: ObjectStorage | None = None,
    ) -> tuple[str, list[dict]]:
        """Scan DocLang XML for embedded base64 data URIs, upload to storage, and replace with asset references.

        Returns:
            sanitized_xml: DocLang XML with data URIs replaced by relative asset paths (e.g. assets/asset_1.png)
            extracted_assets: list of dicts with {"filename": ..., "storage_path": ..., "bytes_len": ..., "asset_bytes": ...}
        """
        if not doclang_xml or "data:image/" not in doclang_xml:
            return doclang_xml, []

        extracted_assets: list[dict] = []
        counter = 0

        def _replace_match(match: re.Match) -> str:
            nonlocal counter
            counter += 1
            ext = match.group("ext").lower()
            if ext == "jpeg":
                ext = "jpg"
            elif ext == "svg+xml":
                ext = "svg"

            raw_b64 = match.group("data").strip()
            try:
                asset_bytes = base64.b64decode(raw_b64)
            except Exception as exc:
                logger.warning("Failed decoding base64 asset #%d: %s", counter, exc)
                return match.group(0)

            asset_filename = f"asset_{counter}.{ext}"
            storage_path = None

            if storage is not None:
                try:
                    storage_path = storage.save_upload(
                        filename=asset_filename,
                        content=asset_bytes,
                        subdir=f"doclang/{doc_key}/assets",
                    )
                except Exception as exc:
                    logger.warning("Failed saving multimodal asset %s to storage: %s", asset_filename, exc)

            extracted_assets.append(
                {
                    "filename": asset_filename,
                    "storage_path": storage_path,
                    "bytes_len": len(asset_bytes),
                    "asset_bytes": asset_bytes,
                }
            )

            return f'src="assets/{asset_filename}"'

        sanitized_xml = DATA_URI_PATTERN.sub(_replace_match, doclang_xml)
        logger.info(
            "Extracted and offloaded %d multimodal assets for doc_key=%s",
            len(extracted_assets),
            doc_key,
        )
        return sanitized_xml, extracted_assets
