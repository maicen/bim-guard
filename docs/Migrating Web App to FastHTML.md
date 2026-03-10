You are an expert Python full-stack developer specializing in FastHTML, HTMX, and modern web architectures.

Your task is to migrate our existing application, \*\*BIM Guard\*\*, from a split Next.js/FastAPI monorepo into a single, cohesive \*\*FastHTML\*\* application.

\#\#\# Context & Current Architecture  
\* \*\*Current Frontend:\*\* Next.js (React, Tailwind CSS, shadcn/ui) located in \`apps/web/\`.  
\* \*\*Current Backend:\*\* FastAPI located in \`apps/api/\`.  
\* \*\*Core Feature:\*\* The app includes a 3D IFC Viewer built with \`@thatopen/components\` (Three.js/WebGL), currently wrapped in React components (\`IFCViewer.tsx\`, \`useBIMViewer.ts\`).  
\* \*\*Business Logic:\*\* Python modules handling IFC parsing, document reading, and rule comparisons (\`apps/api/app/modules/\`).

\#\#\# Target Architecture  
\* \*\*Framework:\*\* FastHTML (Python) serving HTML directly to the browser.  
\* \*\*Interactivity:\*\* HTMX for form submissions, dynamic loading, and state changes.  
\* \*\*Styling:\*\* Tailwind CSS (via CDN script injection in FastHTML).  
\* \*\*3D Viewer:\*\* Vanilla JavaScript served statically. \*\*Crucial Constraint:\*\* Do NOT attempt to rewrite the \`@thatopen/components\` WebGL logic in Python. It must be extracted from React into a Vanilla JS file (\`static/js/ifc-viewer.js\`) and initialized via a FastHTML \`\<script\>\` tag.

\#\#\# Target Directory Structure  
Please organize the new codebase according to this structure:  
\`\`\`text  
bim-guard/  
├── app/  
│ ├── main.py \# FastHTML app init and root routing  
│ ├── components/ \# Reusable FastHTML UI (Layout, Buttons, Cards)  
│ ├── routes/ \# FastHTML route handlers (dashboard, library, viewer)  
│ ├── modules/ \# Existing Python business logic (migrated from apps/api)  
│ └── data/ \# Static data files  
├── static/  
│ ├── js/  
│ │ └── ifc-viewer.js \# Vanilla JS port of the 3D viewer  
│ ├── lib/ \# web-ifc.wasm and worker.mjs  
│ └── css/  
├── pyproject.toml  
└── README.md

### **Step-by-Step Execution Plan**

Please execute the migration in the following phases. Wait for my confirmation after each phase before proceeding to the next.

**Phase 1: Foundation & Layouts**

1. Initialize the FastHTML app in app/main.py using fast_app(hdrs=(tailwind_script,)).
2. Migrate the core layout. Create app/components/layout.py and recreate the Next.js app-sidebar.tsx and app-header.tsx using FastHTML tags (Div, Nav, A, etc.) and their existing Tailwind classes.

**Phase 2: Migrating the 3D IFC Viewer (Vanilla JS Port)**

1. Read apps/web/components/IFCViewer.tsx and apps/web/hooks/useBIMViewer.ts.
2. Convert this React/Hook logic into a clean Vanilla JavaScript module in static/js/ifc-viewer.js. Create an initViewer(containerId) function.
3. Create app/routes/viewer.py. Build a FastHTML route that returns the DashboardLayout containing a Div(id="viewer-container") and injects the ifc-viewer.js script to initialize the canvas. Ensure it points to the WASM files correctly.

**Phase 3: Migrating Pages & HTMX Interactivity**

1. Translate the Dashboard (apps/web/app/(dashboard)/dashboard/page.tsx) into app/routes/dashboard.py.
2. Translate the Rules Library (apps/web/app/(dashboard)/library/rules/page.tsx).
3. Convert the Rule Extraction flow (apps/web/app/(dashboard)/library/rules/extract/page.tsx) into a FastHTML form that uses HTMX (hx_post, hx_target, hx_indicator) to call our backend Python modules and swap the results into the DOM.

**Phase 4: Cleanup**

1. Ensure all business logic from apps/api/app/modules/ is properly imported into the new app/routes/.
2. Provide a summary of the removed apps/web and apps/api folders and the final commands needed to run the new FastHTML server.
