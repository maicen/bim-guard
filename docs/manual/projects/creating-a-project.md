# Creating a Project

1. Go to **Projects** and select **New Project** (or the "+" action).
2. Fill in the project's ISO 19650 identification:
      - **Project code** — the short project identifier used across all documents and models.
      - **Originator**, **volume/system**, **level**, **type**, **role** — governance metadata used to classify project deliverables in the CDE (Common Data Environment).
3. Upload an IFC model, or create the project first and add the model afterwards.
4. Save. The project now appears in the **Projects** list with its current **CDE state**.

## CDE states

Every project and document moves through a governed lifecycle:

`WIP` → `SHARED` → `PUBLISHED` → `ARCHIVED`

State transitions are enforced by the system — you can't skip a state or move backwards without the appropriate permission.

## Next steps

- [Project Settings](project-settings.md)
- [Upload documents to this project](../documents/uploading-documents.md)
- [Run an analysis](../analysis/running-analysis.md)
