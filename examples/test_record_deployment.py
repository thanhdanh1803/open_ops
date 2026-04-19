#!/usr/bin/env python3
"""Exercise `record_deployment` against the SQLite project store.

Why deployments sometimes fail in chat
--------------------------------------
Your traceback shows two ``record_deployment`` log lines (Railway then Vercel),
then ``Recorded deployment`` for Vercel only, then::

    sqlite3.DatabaseError: database disk image is malformed

at ``get_service`` for the *second* tool call. LangGraph's ToolNode often runs
independent tool calls **in parallel threads**. Before OpenOps serialized store
access with a lock, a **single** ``sqlite3`` connection was used from those
threads at once, which could corrupt the DB and surface as
``database disk image is malformed``. The store is now thread-safe; this script
still helps verify sequential vs concurrent tool traffic and check an on-disk
DB with ``PRAGMA integrity_check``.

This script helps you separate:

1. **Healthy DB + sequential calls** — should always succeed.
2. **Shared store + concurrent ``record_deployment``** — may corrupt the DB,
   raise ``DatabaseError``, or even **segfault** the interpreter; this mode runs
   the stress loop in a **subprocess** so your shell stays alive (reproduces the
   risky pattern used when the agent fires two deployment tools at once).
3. **Optional integrity check** — point at your real OpenOps DB and see whether
   it is already corrupt.

Usage (from repo root)::

    python examples/test_record_deployment.py
    python examples/test_record_deployment.py --concurrent
    OPENOPS_DB_PATH=~/.openops/openops.db python examples/test_record_deployment.py --integrity-only

Environment:

- ``OPENOPS_DB_PATH``: if set with ``--integrity-only``, runs ``PRAGMA integrity_check``
  only (no writes).
"""

from __future__ import annotations

import argparse
import logging
import os
import sqlite3
import subprocess
import sys
import tempfile
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def _find_record_deployment_tool(tools: list):
    for t in tools:
        if getattr(t, "name", None) == "record_deployment":
            return t
    raise RuntimeError("record_deployment tool not found in create_project_knowledge_tools()")


def _seed_project_and_services(store, project_path: str) -> tuple[str, str, str]:
    """Return (project_id, service_id_a, service_id_b)."""
    from openops.models import Project, Service

    project_id = str(uuid.uuid4())
    svc_a = str(uuid.uuid4())
    svc_b = str(uuid.uuid4())
    now = datetime.now()

    project = Project(
        id=project_id,
        path=project_path,
        name="example-project",
        description="seed for test_record_deployment",
        keypoints=[],
        analyzed_at=now,
        updated_at=now,
    )
    store.upsert_project(project)

    for sid, name, rel in (
        (svc_a, "frontend", "frontend"),
        (svc_b, "backend", "backend"),
    ):
        store.upsert_service(
            Service(
                id=sid,
                project_id=project_id,
                name=name,
                path=rel,
                description="",
                type="app",
                framework=None,
                language=None,
                version=None,
                entry_point=None,
                build_command=None,
                start_command=None,
                port=None,
                env_vars=[],
                dependencies=[],
                keypoints=[],
            )
        )

    return project_id, svc_a, svc_b


def run_sequential(store_path: str, project_path: str) -> None:
    from openops.agent.tools import create_project_knowledge_tools
    from openops.storage.sqlite_store import SqliteProjectStore

    store = SqliteProjectStore(store_path)
    try:
        _, svc_a, svc_b = _seed_project_and_services(store, project_path)
        tools = create_project_knowledge_tools(store)
        rd = _find_record_deployment_tool(tools)

        r1 = rd.invoke(
            {
                "service_id": svc_a,
                "platform": "vercel",
                "url": "https://example.vercel.app",
                "dashboard_url": "https://vercel.com/dashboard",
            }
        )
        r2 = rd.invoke(
            {
                "service_id": svc_b,
                "platform": "railway",
                "url": "https://api.example.railway.app",
                "dashboard_url": "https://railway.app/project",
            }
        )
        logger.info("Sequential record_deployment results: %s | %s", r1, r2)
        if not (r1.get("success") and r2.get("success")):
            raise SystemExit("Sequential test expected both successes")
        logger.info("Sequential test: OK")
    finally:
        store.close()


def run_concurrent_stress(
    store_path: str,
    svc_a: str,
    svc_b: str,
    iterations: int,
    pair_parallelism: int = 2,
) -> None:
    """Fire parallel ``record_deployment`` calls in small batches.

    LangGraph often runs **two** tool calls at once (e.g. Vercel + Railway). We
    mirror that with batches of ``pair_parallelism`` concurrent tasks instead
    of a large thread pool, which avoids multi-minute ``database is locked``
    stalls while still reproducing cross-thread use of one connection.
    """
    from openops.agent.tools import create_project_knowledge_tools
    from openops.storage.sqlite_store import SqliteProjectStore

    store = SqliteProjectStore(store_path)
    errors: list[BaseException] = []

    def run_tool(tool, service_id: str, platform: str, label: str) -> dict:
        try:
            return tool.invoke(
                {
                    "service_id": service_id,
                    "platform": platform,
                    "url": f"https://{label}.example.test",
                    "dashboard_url": None,
                }
            )
        except BaseException as e:
            errors.append(e)
            raise

    try:
        tools = create_project_knowledge_tools(store)
        rd = _find_record_deployment_tool(tools)

        def task(i: int):
            sid = svc_a if i % 2 == 0 else svc_b
            plat = "vercel" if i % 2 == 0 else "railway"
            return run_tool(rd, sid, plat, f"t{i}")

        for batch_start in range(0, iterations, pair_parallelism):
            with ThreadPoolExecutor(max_workers=pair_parallelism) as ex:
                futures = [
                    ex.submit(task, i) for i in range(batch_start, min(batch_start + pair_parallelism, iterations))
                ]
                for fut in as_completed(futures):
                    try:
                        fut.result()
                    except BaseException as e:
                        logger.warning("Concurrent task failed: %s", e)

        if errors:
            logger.error("Saw %s exception(s) during concurrent test", len(errors))

        ic = store.pragma_integrity_check()
        ok = ic == "ok"
        logger.info("PRAGMA integrity_check after concurrent load: %s", ic)
        if not ok:
            logger.error(
                "Database corrupted after concurrent test. This matches the risk when "
                "the agent runs multiple store-backed tools in parallel on one connection."
            )
            raise SystemExit(2)
        logger.info("Concurrent stress finished (integrity still ok)")
    finally:
        store.close()


def _concurrent_worker_argv() -> None:
    """Internal entry: ``python ... --_concurrent-worker <db> <iterations> <svc_a> <svc_b>``."""
    if len(sys.argv) != 6:
        raise SystemExit("internal worker argv mismatch")
    _, _, db_path, it_s, svc_a, svc_b = sys.argv
    run_concurrent_stress(db_path, svc_a, svc_b, int(it_s))


def run_integrity_only(db_path: str) -> None:
    path = Path(db_path).expanduser()
    if not path.is_file():
        raise SystemExit(f"Not a file: {path}")

    conn = sqlite3.connect(str(path))
    try:
        row = conn.execute("PRAGMA integrity_check").fetchone()
        val = row[0] if row else None
        logger.info("PRAGMA integrity_check for %s: %s", path, val)
        if val != "ok":
            raise SystemExit(
                f"Database is damaged ({val!r}). Back up the file if needed, then remove it or "
                "replace it so OpenOps can create a fresh store."
            )
    finally:
        conn.close()


def main() -> None:
    if len(sys.argv) >= 2 and sys.argv[1] == "--_concurrent-worker":
        _concurrent_worker_argv()
        return

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--concurrent",
        action="store_true",
        help="Run parallel record_deployment calls (may corrupt a temp DB).",
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=30,
        help="Total record_deployment calls for --concurrent (default: 30), run two at a time.",
    )
    parser.add_argument(
        "--integrity-only",
        action="store_true",
        help="Only run PRAGMA integrity_check on OPENOPS_DB_PATH (no writes).",
    )
    args = parser.parse_args()

    if args.integrity_only:
        db = os.environ.get("OPENOPS_DB_PATH")
        if not db:
            raise SystemExit("Set OPENOPS_DB_PATH to your openops SQLite file.")
        run_integrity_only(db)
        return

    project_path = str(Path(__file__).resolve().parent / "mock-project")

    with tempfile.NamedTemporaryFile(prefix="openops_record_deploy_", suffix=".db", delete=False) as f:
        db_path = f.name

    try:
        if args.concurrent:
            logger.info("Seeding temp db, then running concurrent stress in a subprocess: %s", db_path)
            from openops.storage.sqlite_store import SqliteProjectStore

            seed_store = SqliteProjectStore(db_path)
            try:
                _, svc_a, svc_b = _seed_project_and_services(seed_store, project_path)
            finally:
                seed_store.close()

            cmd = [
                sys.executable,
                __file__,
                "--_concurrent-worker",
                db_path,
                str(args.iterations),
                svc_a,
                svc_b,
            ]
            proc = subprocess.run(cmd, cwd=str(Path(__file__).resolve().parent.parent))
            logger.info("Concurrent worker exit code: %s", proc.returncode)
            if proc.returncode in (139, -11):
                logger.error(
                    "Worker exited with a segfault-style code (%s). That is consistent with "
                    "undefined behavior from using one sqlite3 connection from many threads.",
                    proc.returncode,
                )
            elif proc.returncode == 2:
                logger.error("Worker reported database integrity failure after concurrent stress.")
            elif proc.returncode != 0:
                logger.error("Worker failed with exit code %s", proc.returncode)

            try:
                conn = sqlite3.connect(db_path)
                row = conn.execute("PRAGMA integrity_check").fetchone()
                conn.close()
                val = row[0] if row else None
                logger.info("PRAGMA integrity_check on temp db after worker: %s", val)
            except sqlite3.DatabaseError as e:
                logger.error("Could not read temp db after worker (likely corrupted): %s", e)
        else:
            logger.info("Running sequential test on temp db: %s", db_path)
            run_sequential(db_path, project_path)
    finally:
        try:
            os.unlink(db_path)
        except OSError:
            pass


if __name__ == "__main__":
    main()
