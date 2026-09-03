"""
module1_doc_parser/docling_extractor.py
------------------------------------------
Document extraction via a Docling service, an alternative to Unstructured.
Two kinds, both speaking the same protocol:

  - kind "docling"       — a hosted Docling Serve instance, e.g. IBM's
                            managed offering (https://developer.dcls.saas.ibm.com).
                            Requires an API key.
  - kind "docling-local"  — a self-hosted docling-serve Docker container (see
                            docker-compose.yml's `docling-serve` service,
                            profile "docling"; no API key by default —
                            https://github.com/docling-project/docling-serve).

Uses `docling.service_client.DoclingServiceClient` from the `docling-slim`
package — the client-only distribution of Docling. Plain `docling` pulls in
its local conversion pipeline (torch, transformers, opencv, ...) purely to
reach the same `DoclingServiceClient` class; `docling-slim` exposes it with a
lightweight dependency set, since all conversion work happens on the remote
service here, not locally.

Usage:
    from module1_doc_parser.docling_extractor import DoclingExtractor

    # Hosted (default; reads DOCLING_SERVICE_URL/DOCLING_API_KEY)
    extractor = DoclingExtractor()

    # Local docling-serve container, no API key required
    extractor = DoclingExtractor(kind="docling-local", api_url="http://localhost:5001")

    text, tables = extractor.extract("data/input_docs/BuildingCode_Part9.pdf")
"""

from io import BytesIO
from pathlib import Path

KIND_DOCLING_HOSTED = "docling"
KIND_DOCLING_LOCAL = "docling-local"
VALID_KINDS = {KIND_DOCLING_HOSTED, KIND_DOCLING_LOCAL}


class DoclingExtractor:
    """Wraps a Docling Serve instance's synchronous convert() call — hosted or self-hosted."""

    def __init__(
        self,
        api_key: str | None = None,
        api_url: str | None = None,
        kind: str = KIND_DOCLING_HOSTED,
        name: str | None = None,
    ):
        from app.modules.config import DOCLING_API_KEY, DOCLING_SERVICE_URL

        self.kind = (kind or KIND_DOCLING_HOSTED).strip().lower()
        if self.kind not in VALID_KINDS:
            raise ValueError(
                f"Unknown Docling instance kind '{kind}'. Expected one of {sorted(VALID_KINDS)}."
            )

        # The env-var fallback only applies to the hosted kind — it exists so
        # bare `DoclingExtractor()` calls keep working. A local instance with
        # no key configured must stay keyless, never silently inherit a
        # different account's secret meant for the hosted service.
        if self.kind == KIND_DOCLING_HOSTED:
            resolved_key = api_key if api_key is not None else DOCLING_API_KEY
            resolved_url = api_url if api_url is not None else DOCLING_SERVICE_URL
        else:
            resolved_key = api_key or ""
            resolved_url = api_url or ""

        if not resolved_url:
            raise RuntimeError(
                "No Docling service URL configured. Configure a Docling "
                "instance in Settings, or use LightExtractor."
            )
        if self.kind == KIND_DOCLING_HOSTED and not resolved_key:
            raise RuntimeError(
                "DOCLING_API_KEY is not set. Get a key from your Docling "
                "Serve deployment (https://developer.dcls.saas.ibm.com) and "
                "configure it in Settings, or use LightExtractor."
            )

        try:
            from docling.service_client import DoclingServiceClient
        except ImportError as exc:
            raise ImportError(
                "docling-slim not installed. Run: uv add docling-slim"
            ) from exc

        self._client_cls = DoclingServiceClient
        self.api_url = resolved_url
        self.api_key = resolved_key or ""
        self.name = name or self.kind
        print(f"[DoclingExtractor] Ready (kind={self.kind}, instance={self.name})")

    def extract(self, file_path: str | Path, filename: str | None = None) -> tuple:
        """
        Extract text and tables from a document on disk.

        Args:
            file_path (str | Path): path to the document
            filename  (str | None): unused for on-disk paths (Docling reads
                                     the file's own name); kept for parity
                                     with UnstructuredExtractor's signature

        Returns:
            text   (str)
            tables (list[dict])
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        with self._client_cls(url=self.api_url, api_key=self.api_key) as client:
            result = client.convert(source=path)
        return self._result_to_text_and_tables(result, filename or path.name)

    def extract_bytes(self, content: bytes, filename: str) -> tuple:
        """Extract text and tables from raw file bytes via the hosted service."""
        from docling_core.types.io import DocumentStream

        stream = DocumentStream(name=filename, stream=BytesIO(content))
        with self._client_cls(url=self.api_url, api_key=self.api_key) as client:
            result = client.convert(source=stream)
        return self._result_to_text_and_tables(result, filename)

    def _result_to_text_and_tables(self, result, filename: str) -> tuple:
        document = result.document
        text = document.export_to_markdown()

        tables: list[dict] = []
        for table in document.tables:
            dataframe = table.export_to_dataframe(document)
            if dataframe is not None and not dataframe.empty:
                tables.append(
                    {
                        "table_index": len(tables),
                        "dataframe": dataframe,
                        "row_count": len(dataframe),
                        "col_count": len(dataframe.columns),
                    }
                )

        print(f"[DoclingExtractor] Done — {len(text):,} chars, {len(tables)} tables ({filename})")
        return text, tables
