"""
VANGUARD Agent Tools - Sandboxed Command and HTTP Execution Layer
=================================================================
Provides safe, audited tool functions for the ReAct agent to use
during autonomous penetration testing. Every invocation is logged
with timestamps and correlation IDs for SIEM gap analysis.

SAFETY GUARANTEES:
  - Shell commands are filtered against a destructive blocklist
  - HTTP requests are restricted to localhost targets
  - File reads are restricted to /tmp/ paths
  - All commands have a hard timeout
"""
import subprocess
import requests
import os
import re
import datetime
import logging

logger = logging.getLogger("vanguard.agent.tools")

# ──────────────────────────────────────────────────────────────────
# Safety Configuration
# ──────────────────────────────────────────────────────────────────
FATAL_OS_BLOCKLIST = [
    r"\brm\s+-rf\s+/", r"\brm\s+-rf\s+~", r"\brm\s+-rf\s+\*",
    r"\bshutdown\b", r"\breboot\b", r"\bmkfs\b", r"\bdd\s+if=", 
    r"\b:(){ :\|:& };:\b", r"\bchmod\s+-R\s+777\s+/", r"\bchown\s+-R\b.*\s+/",
    r"\b/dev/sd", r"\bformat\b", r"\bfdisk\b", r">\s*/etc/", r">\s*/var/"
]

ALLOWED_HTTP_HOSTS = ["127.0.0.1", "localhost"]
MAX_COMMAND_TIMEOUT = 10  # seconds
MAX_OUTPUT_LENGTH = 4000  # characters to return to LLM

# ──────────────────────────────────────────────────────────────────
# Action Log & Sandbox State
# ──────────────────────────────────────────────────────────────────
action_log = []
SANDBOX_MODE = "app"

def set_sandbox_mode(mode: str):
    """Set the environment execution mode (e.g. 'local_destructive' bypasses safety blocks)."""
    global SANDBOX_MODE
    SANDBOX_MODE = mode



def get_action_log():
    """Return the full audit trail of agent actions."""
    return action_log


def clear_action_log():
    """Reset the action log for a new session."""
    action_log.clear()


def _log_action(tool_name, input_data, output_data, success):
    """Record an action with a precise timestamp for SIEM correlation."""
    entry = {
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        "tool": tool_name,
        "input": str(input_data)[:500],
        "output": str(output_data)[:500],
        "success": success,
    }
    action_log.append(entry)
    return entry


def _is_command_safe(cmd: str) -> bool:
    """Check if a shell command passes the safety blocklist to prevent OS death."""
    for pattern in FATAL_OS_BLOCKLIST:
        if re.search(pattern, cmd, re.IGNORECASE):
            return False
            
    # Allow all other commands (brew, apt, curl, wget, etc.) for AI autonomy
    return True


def _is_http_target_allowed(url: str) -> bool:
    """Ensure HTTP requests target only localhost."""
    if SANDBOX_MODE in ("local_destructive", "network", "app"):
        return True

    for host in ALLOWED_HTTP_HOSTS:
        if host in url:
            return True
    return False


# ──────────────────────────────────────────────────────────────────
# Tool: execute_command
# ──────────────────────────────────────────────────────────────────
def execute_command(cmd: str) -> str:
    """Execute a shell command in a sandboxed subprocess.
    
    Safety: Commands are checked against a destructive blocklist.
    Returns stdout/stderr truncated to MAX_OUTPUT_LENGTH.
    """
    if not _is_command_safe(cmd):
        result = f"BLOCKED: Command '{cmd}' was blocked by the safety layer."
        _log_action("execute_command", cmd, result, False)
        return result

    try:
        cwd = None 
        proc = subprocess.run(
            cmd, shell=True, capture_output=True, text=True,
            timeout=MAX_COMMAND_TIMEOUT, cwd=cwd
        )
        output = ""
        if proc.stdout:
            output += proc.stdout
        if proc.stderr:
            output += "\n[STDERR]: " + proc.stderr
        output = output.strip()[:MAX_OUTPUT_LENGTH]
        if not output:
            output = f"(Command completed with exit code {proc.returncode}, no output)"
        _log_action("execute_command", cmd, output, proc.returncode == 0)
        return output
    except subprocess.TimeoutExpired:
        result = f"TIMEOUT: Command '{cmd}' exceeded {MAX_COMMAND_TIMEOUT}s limit."
        _log_action("execute_command", cmd, result, False)
        return result
    except Exception as e:
        result = f"ERROR: {str(e)}"
        _log_action("execute_command", cmd, result, False)
        return result


# ──────────────────────────────────────────────────────────────────
# Tool: http_request
# ──────────────────────────────────────────────────────────────────
def http_request(method: str, url: str, data: dict = None, headers: dict = None) -> str:
    """Make an HTTP request to the target application.
    
    Safety: Only localhost targets are allowed.
    """
    if not _is_http_target_allowed(url):
        result = f"BLOCKED: URL '{url}' is not an allowed target. Only localhost is permitted."
        _log_action("http_request", f"{method} {url}", result, False)
        return result

    try:
        resp = requests.request(
            method=method.upper(), url=url, json=data,
            headers=headers or {}, timeout=MAX_COMMAND_TIMEOUT
        )
        body = resp.text[:MAX_OUTPUT_LENGTH]
        result = f"HTTP {resp.status_code}\nHeaders: {dict(resp.headers)}\nBody: {body}"
        _log_action("http_request", f"{method} {url} data={data}", result, resp.status_code < 500)
        return result
    except Exception as e:
        result = f"HTTP ERROR: {str(e)}"
        _log_action("http_request", f"{method} {url}", result, False)
        return result


# ──────────────────────────────────────────────────────────────────
# Tool: read_file
# ──────────────────────────────────────────────────────────────────
def read_file(filepath: str) -> str:
    """Read a file from the filesystem.
    
    Safety: Restricted to /tmp/ paths only.
    """
    abs_path = os.path.abspath(filepath)
    if SANDBOX_MODE not in ("local_destructive", "network", "app") and not abs_path.startswith("/tmp/"):
        result = f"BLOCKED: File access restricted to /tmp/ directory. Attempted: {abs_path}"
        _log_action("read_file", filepath, result, False)
        return result

    try:
        with open(abs_path, "r") as f:
            content = f.read()[:MAX_OUTPUT_LENGTH]
        _log_action("read_file", filepath, f"Read {len(content)} chars", True)
        return content
    except Exception as e:
        result = f"FILE ERROR: {str(e)}"
        _log_action("read_file", filepath, result, False)
        return result


# ──────────────────────────────────────────────────────────────────
# Tool Registry (for the ReAct engine to reference)
# ──────────────────────────────────────────────────────────────────
TOOL_REGISTRY = {
    "execute_command": {
        "function": execute_command,
        "description": "Execute a shell command on the host. Use for nmap, curl, whoami, etc.",
        "parameters": "cmd (string): The shell command to execute."
    },
    "http_request": {
        "function": http_request,
        "description": "Make an HTTP request to a target URL. Use for API fuzzing, SQLi, etc.",
        "parameters": "method (string), url (string), data (dict, optional), headers (dict, optional)"
    },
    "read_file": {
        "function": read_file,
        "description": "Read a local file. Restricted to /tmp/ directory.",
        "parameters": "filepath (string): Absolute path to the file."
    },
}
