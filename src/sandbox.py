"""BONUS: safe command execution inside a throwaway Docker container.

Design goals:
- Never run a command that our own safety.py flagged as blocked, or that
  the LLM itself refused / marked unsafe -- callers must pass a
  ConversionResult that already has final_safe_to_show_as_runnable=True.
- Even for "safe" commands, run them in a locked-down, disposable
  container: no network, dropped Linux capabilities, no new privileges,
  read-only root filesystem (except /tmp/work scratch dir), memory/CPU/
  pids limits, and a hard wall-clock timeout. The container is always
  removed afterward.
"""

import io
import tarfile
import time
from dataclasses import dataclass
from typing import Optional

SANDBOX_IMAGE = "python:3.11-slim"
DEFAULT_TIMEOUT_SECONDS = 15


@dataclass
class SandboxRunResult:
    ran: bool
    exit_code: Optional[int]
    stdout: str
    stderr: str
    error: Optional[str] = None
    timed_out: bool = False


def docker_available() -> bool:
    try:
        import docker
        client = docker.from_env()
        client.ping()
        return True
    except Exception:
        return False


def run_in_sandbox(command: str, timeout: int = DEFAULT_TIMEOUT_SECONDS) -> SandboxRunResult:
    """Run `command` inside a locked-down, disposable container.

    Assumes the caller has ALREADY verified the command passed both the
    LLM's own safety self-assessment and safety.check_command(). This
    function does not re-derive that judgement -- it only adds
    container-level isolation as a second layer of protection.
    """
    try:
        import docker
        from docker.errors import ContainerError, ImageNotFound, APIError
    except ImportError:
        return SandboxRunResult(
            ran=False, exit_code=None, stdout="", stderr="",
            error="The 'docker' Python package is not installed. Run: pip install docker",
        )

    try:
        client = docker.from_env()
        client.ping()
    except Exception as e:
        return SandboxRunResult(
            ran=False, exit_code=None, stdout="", stderr="",
            error=f"Docker daemon is not reachable: {e}",
        )

    container = None
    try:
        try:
            client.images.get(SANDBOX_IMAGE)
        except ImageNotFound:
            client.images.pull(SANDBOX_IMAGE)

        container = client.containers.run(
            SANDBOX_IMAGE,
            command=["/bin/sh", "-lc", command],
            detach=True,
            network_disabled=True,
            mem_limit="128m",
            nano_cpus=int(0.5 * 1e9),
            pids_limit=64,
            cap_drop=["ALL"],
            security_opt=["no-new-privileges"],
            read_only=True,
            tmpfs={"/tmp": "size=32m"},
            working_dir="/tmp",
            user="nobody",
            stdout=True,
            stderr=True,
        )

        start = time.time()
        timed_out = False
        try:
            result = container.wait(timeout=timeout)
            exit_code = result.get("StatusCode")
        except Exception:
            timed_out = True
            exit_code = None
            try:
                container.kill()
            except Exception:
                pass

        logs = container.logs(stdout=True, stderr=False).decode("utf-8", errors="replace")
        errs = container.logs(stdout=False, stderr=True).decode("utf-8", errors="replace")

        return SandboxRunResult(
            ran=not timed_out,
            exit_code=exit_code,
            stdout=logs,
            stderr=errs,
            error="Execution timed out and the container was killed" if timed_out else None,
            timed_out=timed_out,
        )
    except (ContainerError, APIError) as e:
        return SandboxRunResult(ran=False, exit_code=None, stdout="", stderr="", error=str(e))
    finally:
        if container is not None:
            try:
                container.remove(force=True)
            except Exception:
                pass
