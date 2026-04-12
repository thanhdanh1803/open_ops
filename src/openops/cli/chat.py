"""Interactive chat command for OpenOps.

Provides a Rich-based chat interface for conversational interaction
with the OpenOps agent.
"""

import logging
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt
from rich.spinner import Spinner
from rich.table import Table

from openops.cli.main import app, show_error
from openops.cli.runtime import OpenOpsRuntime, create_runtime, get_or_create_thread_id
from openops.config import get_config
from openops.exceptions import CredentialError, OpenOpsError

logger = logging.getLogger(__name__)
console = Console()

# Safety cap so a runaway agent cannot prompt forever in one user turn.
_MAX_CHAINED_TOOL_APPROVALS = 100


def _extract_response_content(result: dict) -> str:
    """Extract the assistant's response content from the result."""
    messages = result.get("messages", [])
    if not messages:
        return "No response received."

    last_message = messages[-1]

    if hasattr(last_message, "content"):
        content = last_message.content
    elif isinstance(last_message, dict):
        content = last_message.get("content", str(last_message))
    else:
        content = str(last_message)

    # Handle list content (e.g., multiple content blocks from LLM)
    if isinstance(content, list):
        text_parts = []
        for block in content:
            if isinstance(block, str):
                text_parts.append(block)
            elif isinstance(block, dict) and "text" in block:
                text_parts.append(block["text"])
        return "\n".join(text_parts) if text_parts else str(content)

    return content if isinstance(content, str) else str(content)


def _check_for_interrupt(runtime: OpenOpsRuntime, thread_id: str) -> dict | None:
    """Check if the agent is waiting for approval.

    Returns the pending action if there's an interrupt, None otherwise.
    """
    try:
        state = runtime.get_state(thread_id)
        if state and hasattr(state, "next") and state.next:
            if hasattr(state, "tasks"):
                for task in state.tasks or []:
                    # task is a PregelTask object, not a dict
                    # Check for interrupts attribute on the task object
                    interrupts = getattr(task, "interrupts", None)
                    if interrupts:
                        # Each interrupt is an Interrupt object with a 'value' attribute
                        interrupt = interrupts[0]
                        interrupt_value = getattr(interrupt, "value", interrupt)
                        logger.debug(f"Found interrupt: {interrupt_value}")
                        return interrupt_value
        return None
    except Exception as e:
        logger.debug(f"Error checking interrupt state: {e}")
        return None


def _display_pending_action(action: dict) -> None:
    """Display a pending action that requires approval."""
    table = Table(title="Pending Action", show_header=True, header_style="bold magenta")
    table.add_column("Field", style="cyan")
    table.add_column("Value", style="green")

    # Handle the HITL interrupt structure from deepagents
    # Structure: {'action_requests': [...], 'review_configs': [...]}
    action_requests = action.get("action_requests", [])

    if action_requests:
        for request in action_requests:
            tool_name = request.get("name", "unknown")
            table.add_row("Tool", tool_name)

            args = request.get("args", {})
            for key, value in args.items():
                display_value = str(value)
                table.add_row(f"  {key}", display_value)

            description = request.get("description", "")
            if description:
                table.add_row("Description", description)
    else:
        # Fallback for legacy format
        action_type = action.get("type", "unknown")
        table.add_row("Action", action_type)

        if "tool_name" in action:
            table.add_row("Tool", action["tool_name"])

        if "args" in action:
            for key, value in action["args"].items():
                display_value = str(value)
                table.add_row(f"  {key}", display_value)

    console.print(table)


def _hitl_parallel_action_count(action: dict) -> int:
    """How many tool calls are bundled in one HITL interrupt (needs matching resume decisions)."""
    requests = action.get("action_requests")
    if isinstance(requests, list) and requests:
        return len(requests)
    return 1


def _handle_approval_flow(runtime: OpenOpsRuntime, thread_id: str, action: dict) -> dict | None:
    """Handle the human-in-the-loop approval flow.

    Returns the result after resume, or None if cancelled.
    """
    _display_pending_action(action)
    console.print()

    decision = Prompt.ask(
        "[bold yellow]Decision[/bold yellow]",
        choices=["a", "r", "e"],
        default="a",
    )

    n = _hitl_parallel_action_count(action)
    if n > 1:
        logger.debug("HITL batch resume: %d parallel tool call(s)", n)

    if decision == "a":
        console.print("[green]Approved[/green]")
        return runtime.resume(thread_id, "approve", hitl_action_count=n)
    elif decision == "r":
        reason = Prompt.ask("[yellow]Reason for rejection[/yellow]", default="")
        console.print("[red]Rejected[/red]")
        return runtime.resume(thread_id, "reject", message=reason, hitl_action_count=n)
    else:
        console.print("[yellow]Edit not yet implemented - approving instead[/yellow]")
        return runtime.resume(thread_id, "approve", hitl_action_count=n)


def _show_header(project_path: Path) -> None:
    """Display the chat header."""
    config = get_config()
    console.print(
        Panel(
            f"[bold blue]OpenOps[/bold blue] Interactive Chat\n"
            f"Project: [cyan]{project_path}[/cyan]\n"
            f"Model: [dim]{config.model_provider}/{config.model_name}[/dim]",
            title="Welcome",
            border_style="blue",
        )
    )
    console.print()
    console.print("[dim]Type 'exit', 'quit', or Ctrl+C to exit.[/dim]")
    console.print("[dim]Type 'new' to start a new conversation.[/dim]")
    console.print()


def _show_response(content: str) -> None:
    """Display the agent's response."""
    console.print(
        Panel(
            Markdown(content),
            title="[bold blue]OpenOps[/bold blue]",
            border_style="blue",
        )
    )


def _run_approval_until_idle(runtime: OpenOpsRuntime, thread_id: str) -> None:
    """Prompt for all pending HITL approvals in sequence for this thread.

    After ``resume``, the agent may immediately request another ``execute`` (or
    other gated tool). Without draining interrupts here, the CLI would return
    to the user prompt while the graph is still paused, which makes assistant
    text look ahead of the next approval step.
    """
    for round_idx in range(_MAX_CHAINED_TOOL_APPROVALS):
        interrupt = _check_for_interrupt(runtime, thread_id)
        if not interrupt:
            if round_idx:
                logger.debug("No further tool approvals after %d round(s)", round_idx)
            return

        logger.info(
            "Tool approval required (round %d/%d, thread_id=%s)",
            round_idx + 1,
            _MAX_CHAINED_TOOL_APPROVALS,
            thread_id,
        )
        console.print()
        console.print(
            Panel(
                "[yellow]The agent wants to perform an action that requires your approval.[/yellow]\n"
                "[dim][a]pprove / [r]eject / [e]dit[/dim]",
                title="Approval Required",
                border_style="yellow",
            )
        )
        resume_result = _handle_approval_flow(runtime, thread_id, interrupt)
        if not resume_result:
            logger.debug("Approval flow returned no result; stopping chained approvals")
            return
        content = _extract_response_content(resume_result)
        _show_response(content)

    logger.warning(
        "Chained tool approvals exceeded cap (%d); thread_id=%s",
        _MAX_CHAINED_TOOL_APPROVALS,
        thread_id,
    )
    console.print(
        Panel(
            f"[yellow]Stopped after {_MAX_CHAINED_TOOL_APPROVALS} chained approvals "
            "in one turn. Send another message to continue.[/yellow]",
            title="Approval limit",
            border_style="yellow",
        )
    )


def _chat_loop(runtime: OpenOpsRuntime, thread_id: str, project_path: Path) -> None:
    """Main chat loop."""
    _show_header(project_path)

    while True:
        try:
            console.print()
            user_input = Prompt.ask("[bold green]You[/bold green]")

            if not user_input.strip():
                continue

            lower_input = user_input.lower().strip()
            if lower_input in ("exit", "quit", "q"):
                break

            if lower_input == "new":
                config = get_config()
                thread_id = get_or_create_thread_id(config.data_dir, new=True)
                console.print("[dim]Started new conversation.[/dim]")
                continue

            with Live(
                Spinner("dots", text="Thinking...", style="blue"),
                refresh_per_second=10,
                transient=True,
            ):
                result = runtime.invoke(user_input, thread_id)

            content = _extract_response_content(result)
            _show_response(content)
            _run_approval_until_idle(runtime, thread_id)

        except KeyboardInterrupt:
            console.print("\n[dim]Interrupted[/dim]")
            break
        except OpenOpsError as e:
            show_error(e)
        except Exception as e:
            logger.exception("Error in chat loop")
            show_error(e, hint="Run with --debug for more details")

    console.print()
    console.print("[dim]Goodbye![/dim]")


@app.command()
def chat(
    project_path: Annotated[
        Path | None,
        typer.Argument(
            help="Path to the project directory. Defaults to current directory.",
        ),
    ] = None,
    new_thread: Annotated[
        bool,
        typer.Option(
            "--new",
            "-n",
            help="Start a new conversation thread.",
        ),
    ] = False,
    model: Annotated[
        str | None,
        typer.Option(
            "--model",
            "-m",
            help="Override model for this session (e.g., 'openai:gpt-4o').",
        ),
    ] = None,
) -> None:
    """Start an interactive chat session with OpenOps.

    Chat with the AI agent to deploy, monitor, and manage your projects
    using natural language.

    Examples:

        openops chat                    # Chat in current directory

        openops chat /path/to/project   # Chat with specific project

        openops chat --new              # Start fresh conversation
    """
    project_path = (project_path or Path.cwd()).resolve()

    if not project_path.exists():
        show_error(
            FileNotFoundError(f"Project path does not exist: {project_path}"),
            hint="Check the path and try again.",
        )
        raise typer.Exit(1)

    config = get_config()

    if model:
        parts = model.split(":", 1)
        if len(parts) == 2:
            config.model_provider = parts[0]  # type: ignore
            config.model_name = parts[1]
        else:
            config.model_name = model

    if not config.validate_llm_credentials():
        show_error(
            CredentialError(f"No API key configured for {config.model_provider}"),
            hint=f"Set {config.model_provider.upper()}_API_KEY environment variable or run 'openops init'",
        )
        raise typer.Exit(1)

    config.ensure_data_dir()

    thread_id = get_or_create_thread_id(config.data_dir, new=new_thread)
    logger.info(f"Using thread ID: {thread_id}")

    try:
        runtime = create_runtime(
            working_directory=project_path,
            config=config,
        )
    except Exception as e:
        logger.exception("Failed to create runtime")
        show_error(e, hint="Check your configuration and try again.")
        raise typer.Exit(1) from e

    try:
        _chat_loop(runtime, thread_id, project_path)
    finally:
        runtime.close()


__all__ = ["chat"]
