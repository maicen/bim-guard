"""
module1_doc_parser/unstructured_extractor.py
----------------------------------------------
Step 1 (primary) — document extraction via Unstructured's Workflow/Jobs API.

The account behind UNSTRUCTURED_API_KEY may be a "Transform"/Platform key,
which does not support the classic synchronous single-file Partition
endpoint (`client.general.partition`) — that legacy endpoint is explicitly
unavailable to Pipelines/Platform accounts. Instead this extractor uses the
async Workflow/Jobs API, which the unstructured-client SDK *does* support
for direct file uploads (no S3/cloud source connector required):

    1. Ensure a single, reusable partition-only Workflow exists (created
       once, looked up by name thereafter).
    2. Run that workflow with the file attached as multipart `input_files`
       (`client.workflows.run_workflow`) — this creates an ephemeral Job.
    3. Poll `client.jobs.get_job` until the job reaches a terminal status.
    4. Download the partition node's output elements JSON via
       `client.jobs.download_job_output` (job_id + file_id + node_id — all
       three are required; omitting node_id 404s even though the API
       describes it as optional).

Each call therefore takes on the order of several to tens of seconds
(observed ~20-30s for a trivial document) rather than being instant like
the old synchronous call. Callers needing a fast, synchronous path should
use LightExtractor instead (see document_extractor.py, which already
handles this fallback automatically).

Usage:
    from module1_doc_parser.unstructured_extractor import UnstructuredExtractor
    extractor = UnstructuredExtractor()
    text, tables = extractor.extract("data/input_docs/BuildingCode_Part9.pdf")
"""

import io
import time
from pathlib import Path

_WORKFLOW_NAME = "bimguard-document-extraction"
_POLL_INTERVAL_SECONDS = 2.0
_MAX_WAIT_SECONDS = 300.0
_TERMINAL_FAILURE_STATUSES = {"FAILED", "STOPPED"}


class UnstructuredExtractor:
    """Wraps the Unstructured Workflow/Jobs API (unstructured-client SDK)."""

    def __init__(
        self,
        api_key: str | None = None,
        api_url: str | None = None,
        strategy: str | None = None,
    ):
        from app.modules.config import (
            UNSTRUCTURED_API_KEY,
            UNSTRUCTURED_API_URL,
            UNSTRUCTURED_STRATEGY,
        )

        resolved_key = api_key or UNSTRUCTURED_API_KEY
        if not resolved_key:
            raise RuntimeError(
                "UNSTRUCTURED_API_KEY is not set. Get a key from Unstructured "
                "(https://unstructured.io) and set it in .env, or use LightExtractor."
            )

        try:
            from unstructured_client import UnstructuredClient
        except ImportError as exc:
            raise ImportError(
                "unstructured-client not installed. Run: uv add unstructured-client"
            ) from exc

        client_kwargs = {"api_key_auth": resolved_key}
        resolved_url = api_url or UNSTRUCTURED_API_URL
        if resolved_url:
            client_kwargs["server_url"] = resolved_url

        self.client = UnstructuredClient(**client_kwargs)
        self.strategy = (strategy or UNSTRUCTURED_STRATEGY or "auto").lower()
        self._workflow_id: str | None = None
        print("[UnstructuredExtractor] Ready")

    def extract(self, file_path: str | Path, filename: str | None = None) -> tuple:
        """
        Extract text and tables from a document on disk.

        Args:
            file_path (str | Path): path to the document
            filename  (str | None): filename to report to the API (defaults to
                                     file_path's own name)

        Returns:
            text   (str):        elements' text, concatenated in reading order
            tables (list[dict]): each table as a dict with a DataFrame
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        content = path.read_bytes()
        return self.extract_bytes(content, filename or path.name)

    def extract_bytes(self, content: bytes, filename: str) -> tuple:
        """Extract text and tables from raw file bytes via a Workflow job."""
        from unstructured_client.models import operations, shared

        workflow_id = self._ensure_workflow()

        print(f"[UnstructuredExtractor] Running workflow job: {filename}")
        run_response = self.client.workflows.run_workflow(
            request=operations.RunWorkflowRequest(
                workflow_id=workflow_id,
                body_run_workflow=shared.BodyRunWorkflow(
                    input_files=[
                        shared.BodyRunWorkflowInputFiles(content=content, file_name=filename)
                    ]
                ),
            )
        )
        job_id = run_response.job_information.id
        elements = self._wait_for_elements(job_id)

        text_parts: list[str] = []
        tables: list[dict] = []
        for element in elements:
            el_type = element.get("type", "")
            el_text = (element.get("text") or "").strip()
            metadata = element.get("metadata") or {}
            html_table = metadata.get("text_as_html")

            if el_type == "Table" and html_table:
                dataframe = self._table_html_to_dataframe(html_table)
                if dataframe is not None:
                    tables.append(
                        {
                            "table_index": len(tables),
                            "dataframe": dataframe,
                            "row_count": len(dataframe),
                            "col_count": len(dataframe.columns),
                        }
                    )
                if el_text:
                    text_parts.append(el_text)
            elif el_type == "Title" and el_text:
                text_parts.append(f"# {el_text}")
            elif el_text:
                text_parts.append(el_text)

        text = "\n\n".join(text_parts)
        print(f"[UnstructuredExtractor] Done — {len(text):,} chars, {len(tables)} tables")
        return text, tables

    def _ensure_workflow(self) -> str:
        """Look up the shared partition-only workflow, creating it on first use."""
        if self._workflow_id:
            return self._workflow_id

        from unstructured_client.models import operations, shared

        existing = self.client.workflows.list_workflows(
            request=operations.ListWorkflowsRequest(name=_WORKFLOW_NAME)
        )
        for workflow in existing.response_list_workflows or []:
            if workflow.name == _WORKFLOW_NAME:
                self._workflow_id = workflow.id
                return self._workflow_id

        node = shared.WorkflowNode(
            name="Partitioner",
            subtype="unstructured_api",
            type="partition",
            settings={"strategy": self.strategy},
        )
        created = self.client.workflows.create_workflow(
            request=operations.CreateWorkflowRequest(
                create_workflow=shared.CreateWorkflow(
                    name=_WORKFLOW_NAME,
                    workflow_type=shared.WorkflowType.CUSTOM,
                    workflow_nodes=[node],
                )
            )
        )
        self._workflow_id = created.workflow_information.id
        return self._workflow_id

    def _wait_for_elements(self, job_id: str) -> list:
        """Poll a job to completion and download its partitioned elements JSON."""
        from unstructured_client.models import operations

        deadline = time.monotonic() + _MAX_WAIT_SECONDS
        job = None
        while True:
            response = self.client.jobs.get_job(request=operations.GetJobRequest(job_id=job_id))
            job = response.job_information
            status = job.status.value if hasattr(job.status, "value") else str(job.status)
            status = status.upper()

            if status == "COMPLETED":
                break
            if status in _TERMINAL_FAILURE_STATUSES:
                raise RuntimeError(f"Unstructured job {job_id} ended with status {status}")
            if time.monotonic() > deadline:
                raise TimeoutError(
                    f"Unstructured job {job_id} did not complete within {_MAX_WAIT_SECONDS:.0f}s"
                )
            time.sleep(_POLL_INTERVAL_SECONDS)

        output_files = job.output_node_files or []
        if not output_files:
            return []

        output_file = output_files[-1]
        download_response = self.client.jobs.download_job_output(
            request=operations.DownloadJobOutputRequest(
                job_id=job_id,
                file_id=output_file.file_id,
                node_id=output_file.node_id,
            )
        )
        return download_response.any or []

    @staticmethod
    def _table_html_to_dataframe(html_table: str):
        import pandas as pd

        try:
            return pd.read_html(io.StringIO(html_table))[0]
        except (ValueError, ImportError):
            return None
