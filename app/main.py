from fasthtml.common import *
from app.routes import viewer
from app.components.layout import DashboardLayout

from shad4fast import ShadHead

# Initialize FastHTML app with Shadcn UI headers
app, rt = fast_app(
    pico=False,
    hdrs=(
        ShadHead(tw_cdn=True),
        Style("body { margin: 0; padding: 0; overflow: hidden; }"),
        Script(src="https://unpkg.com/lucide@latest"),
        Link(rel="stylesheet", href="/static/css/styles.css")
    ),
    live=True
)

# Serve static files
@rt("/static/{path:path}")
def serve_static(path: str):
    return FileResponse(f"static/{path}")

# Setup routes
viewer.setup_routes(rt)
from app.routes import dashboard
dashboard.setup_routes(rt)
from app.routes import library
library.setup_routes(rt)

@rt("/")
def get():
    return Title("BIM Guard"), DashboardLayout(
        Div(
            H1("Welcome to BIM Guard", cls="text-2xl font-bold mb-4 tracking-tight"),
            A(Button("Go to Viewer"), href="/viewer"),
            cls="max-w-4xl mx-auto"
        )
    )

if __name__ == '__main__':
    import uvicorn
    uvicorn.run('app.main:app', host='0.0.0.0', port=5001, reload=True)
