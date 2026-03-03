"""
VANGUARD Cognitive Purple Agent - ReAct Engine
===============================================
An autonomous penetration testing agent that uses a Reasoning-and-Acting
(ReAct) loop to interactively discover and exploit vulnerabilities.

The agent:
  1. Receives a target and mission objective
  2. Uses Ollama LLM to reason about the next action
  3. Executes the action via sandboxed tools
  4. Feeds the observation back to the LLM
  5. Repeats until objective is achieved or max steps reached

Every action is timestamped and logged for post-pentest SIEM gap analysis.
"""

import json
import datetime
import logging
import threading
import ollama
from agents.tools import TOOL_REGISTRY, get_action_log, clear_action_log, set_sandbox_mode
from agents.siem_gap_analysis import generate_soc_rules

logger = logging.getLogger("vanguard.agent.react")
OLLAMA_MODEL = "qwen3:8b"
MAX_STEPS = 25

# ──────────────────────────────────────────────────────────────────
# ReAct System Prompt
# ──────────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are VANGUARD, an autonomous AI penetration tester and red team operator.
You are conducting an AUTHORIZED security assessment of a target application.

Your mission: Discover and exploit as many vulnerabilities as possible on the target.
You must think step-by-step, like a real penetration tester performing reconnaissance,
vulnerability discovery, exploitation, and post-exploitation.

AVAILABLE TOOLS:
{tools}

RESPONSE FORMAT:
You MUST respond with ONLY valid JSON (no markdown, no extra text) in this exact format:
{{
    "thought": "Your reasoning about what to do next based on observations",
    "action": "tool_name",
    "input": {{...tool parameters...}}
}}

For execute_command, use: {{"action": "execute_command", "input": {{"cmd": "your command"}}}}
For http_request, use: {{"action": "http_request", "input": {{"method": "GET", "url": "http://...", "data": {{}}}}}}
For read_file, use: {{"action": "read_file", "input": {{"filepath": "/tmp/..."}}}}

When you have completed your assessment, respond with:
{{
    "thought": "Summary of all vulnerabilities found and exploited",
    "action": "FINISH",
    "input": {{"findings": ["Detailed string: Vulnerability name + EXACT leaked data (e.g. passwords, files) extracted"]}}
}}

RULES:
1. Start with reconnaissance — discover what the target exposes.
2. Test each endpoint methodically for common web vulnerabilities.
3. Try SQL injection, path traversal, command injection, IDOR.
4. If you get credentials, try to escalate or access other data.
5. Document your findings clearly in the "thought" field.
6. Be thorough but efficient. You have a maximum of {max_steps} steps.
7. Do NOT output any markdown. Output ONLY the JSON object.
8. TOTAL AUTONOMY: If you need a tool (like nmap, curl, msfconsole, etc.) that is not installed, you are FULLY AUTHORIZED to download and install it yourself using execute_command (e.g. via brew install, apt, or wget/chmod)."""


def _build_tool_descriptions():
    """Build a formatted string of available tools for the system prompt."""
    desc = []
    for name, info in TOOL_REGISTRY.items():
        desc.append(f"  - {name}: {info['description']}\n    Parameters: {info['parameters']}")
    return "\n".join(desc)


def _parse_llm_response(text: str) -> dict:
    """Parse the LLM's JSON response, handling common formatting issues."""
    text = text.strip()
    # Strip markdown code fences if present
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines).strip()
    # Try to find JSON object
    start = text.find("{")
    end = text.rfind("}") + 1
    if start >= 0 and end > start:
        text = text[start:end]
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"thought": text, "action": "PARSE_ERROR", "input": {}}


def _execute_tool(action: str, tool_input: dict) -> str:
    """Dispatch a tool call and return the observation string."""
    if action not in TOOL_REGISTRY:
        return f"ERROR: Unknown tool '{action}'. Available: {list(TOOL_REGISTRY.keys())}"

    tool_fn = TOOL_REGISTRY[action]["function"]
    try:
        if action == "execute_command":
            return tool_fn(tool_input.get("cmd", ""))
        elif action == "http_request":
            req_url = tool_input.get("url", "")
            if not req_url:
                return "ERROR: You must provide a 'url' parameter. Response format must be: {\"action\": \"http_request\", \"input\": {\"method\": \"GET\", \"url\": \"http://...\"}}"
            return tool_fn(
                method=tool_input.get("method", "GET"),
                url=req_url,
                data=tool_input.get("data"),
                headers=tool_input.get("headers"),
            )
        elif action == "read_file":
            return tool_fn(tool_input.get("filepath", ""))
        else:
            return f"ERROR: Tool '{action}' has no handler."
    except Exception as e:
        return f"TOOL ERROR: {str(e)}"

def generate_attack_chain_mermaid(steps: list) -> str:
    """Dynamically build a Mermaid.js graph string based on the agent's actual execution path."""
    lines = [
        "graph TD", 
        "  classDef recon fill:#1e3a8a,stroke:#3b82f6,stroke-width:2px,color:#fff;",
        "  classDef exploit fill:#7f1d1d,stroke:#ef4444,stroke-width:2px,color:#fff;",
        "  classDef target fill:#064e3b,stroke:#10b981,stroke-width:2px,color:#fff;"
    ]
    
    lines.append("  Start((Mission Start)):::target")
    prev_id = "Start"
    
    for s in steps:
        if "input" not in s: 
            continue
        step_id = f"Step{s['step']}"
        action_type = s['action']
        
        node_class = "recon" if action_type in ["read_file", "http_request"] else "exploit"
            
        label = action_type
        if action_type == "execute_command":
            cmd = s['input'].get('cmd', '')
            label = f"execute: {cmd}"
        elif action_type == "http_request":
            method = s['input'].get('method', 'GET')
            url = s['input'].get('url', '')
            path = url.split('/')[-1] if '/' in url else url
            label = f"{method} {path}"
            
        label = label.replace('"', "'").replace('[', '(').replace(']', ')')
        # Mermaid nodes cannot start with numbers easily or have unescaped hyphens in keys, 
        # but since we wrap in quotes `step_id["label"]`, it should be safe. However, 
        # let's strip newlines and excessive whitespace just in case.
        label = " ".join(label.split())
        lines.append(f"  {prev_id} -->|Step {s['step']}| {step_id}[\"{label}\"]:::{node_class}")
        prev_id = step_id
        
    lines.append(f"  {prev_id} --> End((Assessment Complete)):::target")
    return "\n".join(lines)


# ──────────────────────────────────────────────────────────────────
# Main ReAct Loop
# ──────────────────────────────────────────────────────────────────
def run_react_pentest(target_url: str, mission: str = None, max_steps: int = MAX_STEPS, scope: str = "app", on_step_callback=None, cancel_event: threading.Event = None):
    """Run the autonomous ReAct penetration testing loop.
    
    Args:
        target_url: The base URL of the target
        mission: Optional mission description override
        max_steps: Maximum number of reasoning steps
        scope: Engagement scope ('app', 'local_destructive')
        on_step_callback: Callable to stream live events back to the UI
        cancel_event: threading.Event to signal cancellation from outside
    """
    clear_action_log()
    set_sandbox_mode(scope)
    
    if not mission:
        mission = (
            f"Conduct a full penetration test against {target_url}. "
            "Discover all exposed endpoints, test for SQL injection, "
            "path traversal, command injection, IDOR, and information disclosure. "
            "Exploit every vulnerability you find. Extract any sensitive data."
        )

    system_msg = SYSTEM_PROMPT.format(
        tools=_build_tool_descriptions(),
        max_steps=max_steps
    )

    # Conversation history for the LLM
    messages = [
        {"role": "system", "content": system_msg},
        {"role": "user", "content": f"TARGET: {target_url}\nMISSION: {mission}\n\nBegin your assessment. Step 1:"}
    ]

    start_time = datetime.datetime.utcnow()
    findings = []
    steps = []

    print("\n" + "=" * 70)
    print("  🧠 VANGUARD COGNITIVE PURPLE AGENT — ReAct Penetration Test")
    print(f"  Target: {target_url}")
    print(f"  Max Steps: {max_steps}")
    print("=" * 70)

    for step_num in range(1, max_steps + 1):
        # Check for cancellation at the top of every step
        if cancel_event and cancel_event.is_set():
            print(f"\n  🛑 SCAN CANCELLED by user at step {step_num}")
            if on_step_callback:
                on_step_callback({"type": "finish", "data": f"Scan cancelled by user at step {step_num}."})
            break

        print(f"\n{'─' * 60}")
        print(f"  STEP {step_num}/{max_steps}")
        print(f"{'─' * 60}")

        # Ask the LLM for its next action
        try:
            response = ollama.chat(
                model=OLLAMA_MODEL,
                messages=messages,
                format="json",
            )
            raw_content = response["message"]["content"]
        except Exception as e:
            print(f"  [!] LLM Error: {e}")
            break

        parsed = _parse_llm_response(raw_content)
        thought = parsed.get("thought", "No thought provided")
        action = parsed.get("action", "PARSE_ERROR")
        tool_input = parsed.get("input", {})

        print(f"  💭 Thought: {thought[:200]}")
        print(f"  ⚡ Action:  {action}")

        if on_step_callback:
            on_step_callback({"type": "thought", "data": thought})
            action_data = f"{action}"
            if tool_input:
                action_data += f" | {json.dumps(tool_input)}"
            on_step_callback({"type": "action", "data": action_data})

        if action == "FINISH":
            findings = tool_input.get("findings", [thought])
            print(f"\n  ✅ AGENT FINISHED — {len(findings)} findings reported")
            steps.append({"step": step_num, "thought": thought, "action": action, "findings": findings})
            if on_step_callback:
                chain_mermaid = generate_attack_chain_mermaid(steps)
                on_step_callback({"type": "chain", "data": chain_mermaid})
                on_step_callback({"type": "findings", "data": findings})
                
                # Dynamic Purple Teaming: Generate and stream SOC Rules based on the attack log
                soc_rules = generate_soc_rules(get_action_log())
                if soc_rules:
                    on_step_callback({"type": "soc_rules", "data": soc_rules})
                    
                new_rule_count = len(soc_rules.get('newly_generated_rules', []))
                on_step_callback({"type": "finish", "data": f"Assessment complete. Found {len(findings)} vulnerabilities and wrote {new_rule_count} SOC Rules."})
            break

        if action == "PARSE_ERROR":
            # Feed the error back and let the LLM retry
            messages.append({"role": "assistant", "content": raw_content})
            messages.append({"role": "user", "content": "ERROR: Your response was not valid JSON. Please respond with ONLY a valid JSON object."})
            steps.append({"step": step_num, "thought": thought, "action": action, "observation": "Parse error"})
            if on_step_callback:
                on_step_callback({"type": "observation", "data": "Parse error. Retrying..."})
            continue

        # Execute the tool
        if isinstance(tool_input, str):
            tool_input = {"cmd": tool_input} if action == "execute_command" else {"url": tool_input}
        
        print(f"  📥 Input:   {str(tool_input)[:200]}")
        observation = _execute_tool(action, tool_input)
        print(f"  📤 Output:  {observation[:300]}")

        if on_step_callback:
            on_step_callback({"type": "observation", "data": observation[:500]})

        # Record this step
        steps.append({
            "step": step_num,
            "thought": thought,
            "action": action,
            "input": tool_input,
            "observation": observation[:500],
        })

        # Feed the observation back to the LLM for the next reasoning step
        messages.append({"role": "assistant", "content": raw_content})
        messages.append({"role": "user", "content": f"OBSERVATION:\n{observation}\n\nContinue your assessment. Step {step_num + 1}:"})

    end_time = datetime.datetime.utcnow()

    result = {
        "target": target_url,
        "mission": mission,
        "findings": findings,
        "steps": steps,
        "action_log": get_action_log(),
        "start_time": start_time.isoformat() + "Z",
        "end_time": end_time.isoformat() + "Z",
        "total_steps": len(steps),
        "duration_seconds": (end_time - start_time).total_seconds(),
    }

    print(f"\n{'=' * 70}")
    print(f"  Assessment Complete: {len(steps)} steps, {len(findings)} findings")
    print(f"  Duration: {result['duration_seconds']:.1f}s")
    print(f"{'=' * 70}\n")

    return result
