# Installing Docker

BIM-Guard's self-hosted stack (Supabase, Neo4j, Docling, and the app itself) runs
via **Docker Compose**. This page gets Docker installed and working on your
machine; once it's done, head back to the
[Contributor Quickstart](https://github.com/maicen/bim-guard#contributor-quickstart-local-docker-no-external-accounts-needed)
in the repository README.

You only need this if you're using the Docker path. Running the backend and
frontend directly (`uv run uvicorn` / `npm run dev`, see
[Environment Setup](environment-setup.md)) doesn't require Docker at all.

=== "macOS"

    **Option A — Docker Desktop** (most common):

    1. Download and install [Docker Desktop for Mac](https://www.docker.com/products/docker-desktop/) (choose Apple Silicon or Intel).
    2. Launch Docker Desktop from Applications and wait for the whale icon in the menu bar to show "Docker Desktop is running".
    3. Verify from a terminal:
       ```bash
       docker --version
       docker compose version
       ```

    **Option B — [OrbStack](https://orbstack.dev/)** (lighter-weight alternative, what BIM-Guard's own production host uses):

    1. `brew install orbstack` (or download from orbstack.dev).
    2. Launch OrbStack once to finish setup — it provides a drop-in Docker Engine plus `docker`/`docker compose` CLIs.
    3. Verify the same way: `docker --version && docker compose version`.

    Both options support `host.docker.internal` out of the box, which BIM-Guard's
    Compose setup relies on (e.g. to reach a locally-installed Ollama server from
    inside the container).

=== "Windows"

    Docker Desktop on Windows needs **WSL2** (Windows Subsystem for Linux) as its backend.

    1. Install WSL2 if you don't have it — open PowerShell as Administrator:
       ```powershell
       wsl --install
       ```
       Reboot when prompted.
    2. Download and install [Docker Desktop for Windows](https://www.docker.com/products/docker-desktop/).
    3. During setup, ensure **"Use WSL 2 instead of Hyper-V"** is enabled (default on modern Docker Desktop).
    4. Launch Docker Desktop and wait for it to report "Docker Desktop is running".
    5. Verify from PowerShell or a WSL2 terminal:
       ```powershell
       docker --version
       docker compose version
       ```

    Run the project's own commands (`docker compose up --build`, `uv sync`, etc.) from
    **inside your WSL2 distro** (e.g. Ubuntu), not from native PowerShell/cmd — this
    matches how the rest of BIM-Guard's tooling (`run_server.sh`, `uv`) expects a
    POSIX shell, and avoids filesystem performance issues from crossing the
    Windows/WSL boundary.

=== "Linux"

    Install Docker Engine plus the Compose plugin directly (no Docker Desktop needed):

    1. Follow the official install guide for your distribution — e.g. for Ubuntu/Debian:
       ```bash
       curl -fsSL https://get.docker.com | sh
       ```
       Or follow [Docker's distro-specific instructions](https://docs.docker.com/engine/install/) for exact package-manager steps.
    2. Add your user to the `docker` group so you don't need `sudo` for every command (log out/in afterward):
       ```bash
       sudo usermod -aG docker $USER
       ```
    3. Verify:
       ```bash
       docker --version
       docker compose version
       ```
    4. **`host.docker.internal`**: unlike Docker Desktop/OrbStack, plain Docker Engine on
       Linux doesn't resolve this automatically — but BIM-Guard's `docker-compose.yml`
       already declares the `extra_hosts: host.docker.internal:host-gateway` mapping
       needed to make it work (Compose 2.1+ / Docker 20.10+), so no extra setup is
       required on your end.

## Verify everything works

From the repository root, after [copying your `.env` files](https://github.com/maicen/bim-guard#contributor-quickstart-local-docker-no-external-accounts-needed):

```bash
docker compose config    # validates the compose files parse; prints nothing on success
docker compose up --build
```

If `docker compose up` fails immediately with a port-in-use error, something else on
your machine is already bound to `8000`, `5173`, `54321`–`54323`, `7474`/`7687`, or
`5001` — stop that process or adjust the relevant port in your `.env`.

## Troubleshooting

- **`Cannot connect to the Docker daemon`**: Docker Desktop/OrbStack isn't running — launch it and wait for it to report ready.
- **Permission denied on `/var/run/docker.sock`** (Linux): you weren't added to the `docker` group yet, or haven't logged out/in since being added.
- **Slow builds / high CPU on macOS**: increase the memory/CPU allocation in Docker Desktop's Resources settings, or switch to OrbStack, which is generally lighter.
- **`failed to read env_file docker/supabase/.env`**: you skipped the `cp docker/supabase/.env.example docker/supabase/.env` step in the Quickstart.
