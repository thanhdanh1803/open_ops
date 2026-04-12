#!/usr/bin/env python3
"""Test script to verify shell execution works in the OpenOps agent.

This script tests the LocalShellBackend to ensure shell commands can be executed
properly. Run this to diagnose issues with command execution.

FINDINGS:
---------
1. LocalShellBackend.execute() works correctly
2. Agent with interrupt_on={} executes commands immediately
3. Agent with interrupt_on={'execute': True} triggers HITL interrupt
4. HITL interrupt must be handled with Command(resume={'decisions': [{'type': 'approve'}]})

The main bug was in chat.py:_check_for_interrupt() - it was treating PregelTask
objects as dicts (task.get("interrupts")) instead of accessing the attribute
(task.interrupts). This caused the CLI to miss HITL interrupts entirely.

Usage:
    cd /Users/danhmac/Documents/open_ops
    python examples/test_shell_execution.py
"""

import logging
import os
import sys
from pathlib import Path

# Add src to path for local development
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def test_local_shell_backend():
    """Test LocalShellBackend directly."""
    from deepagents.backends import LocalShellBackend

    logger.info("=== Testing LocalShellBackend ===")

    backend = LocalShellBackend(
        root_dir=str(Path.cwd()),
        env={"PATH": os.environ.get("PATH", "/usr/bin:/bin")},
        virtual_mode=False,  # Explicit to avoid deprecation warning
    )
    logger.info(f"Created LocalShellBackend with cwd={backend.cwd}")

    # Test simple commands using backend.execute() directly
    test_commands = [
        ("echo 'Hello from shell'", "Basic echo"),
        ("pwd", "Print working directory"),
        ("npm --version", "Check npm version"),
        ("node --version", "Check node version"),
        ("which npm", "Find npm path"),
    ]

    results = []
    for cmd, description in test_commands:
        logger.info(f"\n--- Testing: {description} ---")
        logger.info(f"Command: {cmd}")

        try:
            result = backend.execute(cmd)
            logger.info(f"Result type: {type(result)}")
            logger.info(f"Result: {result}")
            results.append((cmd, True, result))
        except Exception as e:
            logger.error(f"Error executing command: {e}")
            import traceback

            traceback.print_exc()
            results.append((cmd, False, str(e)))

    # Summary
    logger.info("\n=== Summary ===")
    for cmd, success, result in results:
        status = "✓" if success else "✗"
        result_str = str(result)[:100] if result else "None"
        logger.info(f"{status} {cmd}: {result_str}...")

    return all(success for _, success, _ in results[:2])  # At least echo and pwd should work


def test_agent_with_shell():
    """Test a minimal agent that uses shell execution."""
    from deepagents import create_deep_agent
    from deepagents.backends import LocalShellBackend
    from langgraph.checkpoint.memory import MemorySaver

    logger.info("\n=== Testing Agent with Shell Execution ===")

    # Check for API key - support multiple providers
    model = None
    if os.environ.get("ANTHROPIC_API_KEY"):
        from langchain_anthropic import ChatAnthropic

        model = ChatAnthropic(model="claude-sonnet-4-20250514")
        logger.info("Using Anthropic model")
    elif os.environ.get("OPENAI_API_KEY"):
        from langchain_openai import ChatOpenAI

        model = ChatOpenAI(model="gpt-4o-mini")
        logger.info("Using OpenAI model")
    else:
        logger.warning("No API key found (ANTHROPIC_API_KEY or OPENAI_API_KEY), skipping agent test")
        return None

    backend = LocalShellBackend(
        root_dir=str(Path.cwd()),
        env={"PATH": os.environ.get("PATH", "/usr/bin:/bin")},
        virtual_mode=False,
    )

    agent = create_deep_agent(
        name="test-shell-agent",
        model=model,
        system_prompt="""You are a test agent. When asked to run a command,
        use the execute tool to run it and report the result.
        Always actually execute commands - never just describe what you would do.
        You MUST use the execute tool - do not just say what you would run.""",
        tools=[],
        backend=backend,
        checkpointer=MemorySaver(),
        interrupt_on={},  # No interrupts - execute immediately
    )
    logger.info(f"Created agent: {agent}")

    logger.info("Created test agent")

    # Test the agent
    config = {"configurable": {"thread_id": "test-1"}}

    try:
        logger.info("Invoking agent with: 'Run npm --version and tell me the result'")
        result = agent.invoke(
            {"messages": [{"role": "user", "content": "Run npm --version and tell me the result"}]},
            config=config,
        )
        logger.info(f"Agent response: {result}")

        # Extract the last message
        messages = result.get("messages", [])
        if messages:
            last_msg = messages[-1]
            logger.info(f"Last message content: {last_msg.content if hasattr(last_msg, 'content') else last_msg}")

        return True
    except Exception as e:
        logger.error(f"Agent invocation failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_hitl_interrupt():
    """Test if HITL interrupts are blocking execution."""
    from deepagents import create_deep_agent
    from deepagents.backends import LocalShellBackend
    from langgraph.checkpoint.memory import MemorySaver

    logger.info("\n=== Testing HITL Interrupt Behavior ===")

    # Check for API key - support multiple providers
    model = None
    if os.environ.get("ANTHROPIC_API_KEY"):
        from langchain_anthropic import ChatAnthropic

        model = ChatAnthropic(model="claude-sonnet-4-20250514")
        logger.info("Using Anthropic model")
    elif os.environ.get("OPENAI_API_KEY"):
        from langchain_openai import ChatOpenAI

        model = ChatOpenAI(model="gpt-4o-mini")
        logger.info("Using OpenAI model")
    else:
        logger.warning("No API key found, skipping HITL test")
        return None

    backend = LocalShellBackend(
        root_dir=str(Path.cwd()),
        env={"PATH": os.environ.get("PATH", "/usr/bin:/bin")},
        virtual_mode=False,
    )

    # Create agent WITH interrupt on execute (like the real orchestrator)
    agent = create_deep_agent(
        name="test-hitl-agent",
        model=model,
        system_prompt="You are a test agent. Use the execute tool to run shell commands.",
        tools=[],
        backend=backend,
        checkpointer=MemorySaver(),
        interrupt_on={"execute": True},  # This is what the orchestrator uses
    )

    logger.info("Created agent with interrupt_on={'execute': True}")

    config = {"configurable": {"thread_id": "test-hitl-1"}}

    try:
        logger.info("Invoking agent...")
        result = agent.invoke(
            {"messages": [{"role": "user", "content": "Run echo hello"}]},
            config=config,
        )
        logger.info(f"Initial result: {result}")

        # Check if we hit an interrupt
        state = agent.get_state(config)
        logger.info(f"Agent state after invoke: {state}")

        if hasattr(state, "tasks") and state.tasks:
            logger.info("Agent is waiting for HITL approval!")
            logger.info(f"Pending tasks: {state.tasks}")

            # Resume with approval
            from langgraph.types import Command

            logger.info("Resuming with approval...")
            result = agent.invoke(
                Command(resume={"decisions": [{"type": "approve"}]}),
                config=config,
            )
            logger.info(f"Result after approval: {result}")

        return True
    except Exception as e:
        logger.error(f"HITL test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    logger.info("Starting shell execution tests...\n")

    # Test 1: Direct backend test
    backend_ok = test_local_shell_backend()
    logger.info(f"\nBackend test: {'PASSED' if backend_ok else 'FAILED'}")

    # Test 2: Agent test (if API key available)
    agent_ok = test_agent_with_shell()
    if agent_ok is not None:
        logger.info(f"Agent test: {'PASSED' if agent_ok else 'FAILED'}")

    # Test 3: HITL test
    hitl_ok = test_hitl_interrupt()
    if hitl_ok is not None:
        logger.info(f"HITL test: {'PASSED' if hitl_ok else 'FAILED'}")

    logger.info("\n=== All tests complete ===")
