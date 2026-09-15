# Getting Started

## What you need

- Access to the BIM-Guard web app URL (or a local install — see [Environment Setup](infrastructure/environment-setup.md)).
- A user account. New accounts are created via Google sign-in or email/password self-serve sign-up on the login screen.

## Signing in

1. Open the BIM-Guard app in your browser.
2. On the login screen, sign in with **Google**, or **email and password** if you already created an account.
3. New to the app? Use the sign-up option on the same screen to create an account — it's added the same way as a Google sign-in.

!!! tip "Local development only"
    If you're running BIM-Guard locally for development, a seeded **"Sign in as dev test user"** button appears automatically — see `CLAUDE.md` in the repository for details. This shortcut does not exist in production.

## The main views

After signing in you land on the main dashboard, with navigation to:

- **Projects** — your IFC building projects.
- **Documents** — uploaded PDFs and extracted text linked to a project.
- **Rules** — the compliance rules catalog (galvanic corrosion, crevice corrosion, microbiological corrosion, ISO 19650 governance, etc.).
- **Reports & BCF Topics** — analysis findings and issue tracking.
- **Revit Sync** — synchronization status with Revit-originated models.

## Next steps

- [Create your first project](projects/creating-a-project.md)
- [Upload a document](documents/uploading-documents.md)
- [Run an analysis](analysis/running-analysis.md)
