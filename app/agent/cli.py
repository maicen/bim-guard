"""Interactive Python terminal interface for the BIM Guard agent."""

import argparse
import asyncio
import itertools
import sys
import threading
import time

from app.agent.config import AgentConfig
from app.agent.runner import OpenRouterAgent
from app.services.llm_model_service import LLMModelService

RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"


class Spinner:
    """Small terminal spinner used while waiting for OpenRouter."""

    def __init__(self, text: str = "Working") -> None:
        """Configure spinner text."""
        self.text = text
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        """Start rendering spinner frames."""
        def render():
            for frame in itertools.cycle("⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"):
                if self._stop.wait(0.08):
                    break
                sys.stdout.write(f"\r{CYAN}{frame}{RESET} {DIM}{self.text}{RESET}")
                sys.stdout.flush()

        self._thread = threading.Thread(target=render, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop rendering and clear the spinner line."""
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=0.2)
        sys.stdout.write("\r\033[K")
        sys.stdout.flush()


def _print_banner(config: AgentConfig) -> None:
    width = min(64, max(40, len(config.model) + 12))
    line = "─" * width
    print(f"\n{DIM}{line}{RESET}")
    print(f"  {BOLD}BIM Guard Agent{RESET}  {DIM}Python · OpenRouter{RESET}")
    print(f"  {DIM}model{RESET}  {CYAN}{config.model}{RESET}")
    print(f"  {DIM}/model · /new · /help · exit{RESET}")
    print(f"{DIM}{line}{RESET}\n")


def _get_input() -> str:
    width = 64
    print(f"{DIM}{'─' * width}{RESET}")
    value = input(f"{GREEN}›{RESET} ")
    print(f"{DIM}{'─' * width}{RESET}")
    return value


def _tool_event(event: str, payload: dict) -> None:
    if event == "tool_call":
        summary = next(iter(payload["arguments"].values()), "")
        summary = str(summary)
        if len(summary) > 70:
            summary = summary[:70] + "..."
        print(f"  {YELLOW}├─{RESET} {BOLD}{payload['name']}{RESET} {DIM}{summary}{RESET}")
    elif event == "tool_result":
        print(f"  {GREEN}└─ done{RESET} {DIM}{payload['name']}{RESET}")


async def _choose_model(agent: OpenRouterAgent) -> None:
    spinner = Spinner("Loading OpenRouter models")
    spinner.start()
    try:
        models = await LLMModelService().list_models(
            "openrouter", api_key=agent.config.api_key
        )
    finally:
        spinner.stop()
    if not models:
        print(f"{YELLOW}No OpenRouter models were returned.{RESET}")
        return
    query = input("Filter models (blank for first 20): ").strip().casefold()
    filtered = [item for item in models if query in f"{item[0]} {item[1]}".casefold()]
    shown = filtered[:20]
    for index, (model_id, label) in enumerate(shown, start=1):
        print(f"  {index:>2}. {label} {DIM}{model_id}{RESET}")
    choice = input("Model number (blank to cancel): ").strip()
    if not choice:
        return
    try:
        agent.config.model = shown[int(choice) - 1][0]
    except (ValueError, IndexError):
        print(f"{YELLOW}Invalid model selection.{RESET}")
        return
    print(f"Model changed to {CYAN}{agent.config.model}{RESET}")


async def run_cli(args: argparse.Namespace) -> None:
    """Run the interactive agent until the user exits."""
    config = AgentConfig.from_env()
    if args.model:
        config.model = args.model
    if args.max_steps is not None:
        config.max_steps = args.max_steps
    if args.max_cost is not None:
        config.max_cost = args.max_cost
    if args.no_web_search:
        config.web_search = False
    agent = OpenRouterAgent(config)
    _print_banner(config)

    while True:
        try:
            prompt = _get_input().strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if not prompt:
            continue
        command = prompt.casefold()
        if command in {"exit", "quit"}:
            return
        if command == "/help":
            print("/model  choose an available OpenRouter model")
            print("/new    start a fresh conversation and session")
            print("/help   show commands")
            print("exit    close the agent")
            continue
        if command == "/new":
            agent.reset()
            print(f"New session: {agent.session.id}")
            continue
        if command == "/model":
            try:
                await _choose_model(agent)
            except Exception as exc:
                print(f"{YELLOW}Could not load models: {exc}{RESET}")
            continue

        spinner = Spinner()
        spinner.start()
        started = time.perf_counter()

        def handle_event(event: str, payload: dict) -> None:
            spinner.stop()
            _tool_event(event, payload)

        try:
            answer = await agent.run(prompt, on_event=handle_event)
        except Exception as exc:
            spinner.stop()
            print(f"{YELLOW}Error: {exc}{RESET}\n")
            continue
        spinner.stop()
        print(f"{answer}\n")
        print(
            f"{DIM}{time.perf_counter() - started:.1f}s · "
            f"${agent.total_cost:.4f} · session {agent.session.id}{RESET}\n"
        )


def main() -> None:
    """Console-script entry point."""
    parser = argparse.ArgumentParser(
        prog="bim-guard-agent",
        description="Run the Python BIM Guard agent through OpenRouter.",
    )
    parser.add_argument("--model", help="OpenRouter model ID (default: openrouter/auto)")
    parser.add_argument("--max-steps", type=int, help="Maximum model/tool turns")
    parser.add_argument("--max-cost", type=float, help="Maximum session cost in USD")
    parser.add_argument(
        "--no-web-search",
        action="store_true",
        help="Disable OpenRouter's server-side web search plugin",
    )
    asyncio.run(run_cli(parser.parse_args()))


if __name__ == "__main__":
    main()