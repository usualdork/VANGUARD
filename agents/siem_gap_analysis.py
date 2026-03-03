"""
VANGUARD SIEM Gap Analysis Engine
==================================
After the Cognitive Purple Agent completes its autonomous penetration test,
this module correlates the agent's action log against the Elasticsearch
SIEM to determine which attack actions were detected and which evaded.

Produces a quantified Detection Gap Report showing:
  - Each attack action with timestamp
  - Whether the SIEM generated a corresponding alert
  - Time-To-Detect (TTD) for detected actions
  - Blind spots where the SOC failed to detect the attack
"""

import datetime
import json
import logging
import requests

import re

logger = logging.getLogger("vanguard.siem_analysis")

# Lazy Elasticsearch client — retries connection on every call
_es_client = None
_es_available = None  # None = not checked, True/False = cached result

def get_es():
    """Lazy Elasticsearch client. Retries connection each time if previously failed."""
    global _es_client, _es_available
    try:
        from elasticsearch import Elasticsearch
        if _es_client is not None and _es_available:
            return _es_client
        client = Elasticsearch("http://127.0.0.1:9200")
        if client.ping():
            _es_client = client
            _es_available = True
            print("  ✅ Elasticsearch connected successfully.")
            return client
        else:
            _es_available = False
            print("  ⚠️  Elasticsearch ping failed.")
            return None
    except Exception as e:
        _es_available = False
        print(f"  ⚠️  Elasticsearch client error: {e}")
        return None


def index_agent_actions(action_log: list, correlation_id: str):
    """Push all agent actions into the vanguard-telemetry index for SIEM visibility."""
    es = get_es()
    if not es:
        logger.warning("Elasticsearch unavailable. Skipping telemetry indexing.")
        return 0

    indexed = 0
    for action in action_log:
        doc = {
            "timestamp": action["timestamp"],
            "event_type": "agent_action",
            "correlation_id": correlation_id,
            "tool": action["tool"],
            "input": action["input"],
            "output": action["output"][:200],
            "success": action["success"],
            "source": "cognitive_purple_agent",
        }
        try:
            es.index(index="vanguard-telemetry", document=doc)
            indexed += 1
        except Exception as e:
            logger.error(f"Failed to index action: {e}")
    return indexed


def index_findings_as_alerts(findings: list, correlation_id: str, start_time: str, end_time: str):
    """Push the agent's vulnerability findings into vanguard-alerts as high-severity events."""
    es = get_es()
    if not es:
        logger.warning("Elasticsearch unavailable. Skipping alert indexing.")
        return 0

    indexed = 0
    for i, finding in enumerate(findings):
        doc = {
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
            "event_type": "vulnerability_finding",
            "severity": "critical",
            "correlation_id": correlation_id,
            "finding_index": i + 1,
            "description": finding if isinstance(finding, str) else json.dumps(finding),
            "source": "cognitive_purple_agent",
            "pentest_start": start_time,
            "pentest_end": end_time,
        }
        try:
            es.index(index="vanguard-alerts", document=doc)
            indexed += 1
        except Exception as e:
            logger.error(f"Failed to index finding: {e}")
    return indexed


def query_siem_detections(start_time: str, end_time: str, correlation_id: str) -> list:
    """Query Elasticsearch for any Blue Sensor detections during the pentest window."""
    es = get_es()
    if not es:
        return []

    try:
        query = {
            "bool": {
                "must": [
                    {"range": {"timestamp": {"gte": start_time, "lte": end_time}}},
                ]
            }
        }
        result = es.search(index="vanguard-alerts", query=query, size=100)
        return [hit["_source"] for hit in result["hits"]["hits"]]
    except Exception as e:
        logger.error(f"SIEM query failed: {e}")
        return []


def generate_gap_report(pentest_result: dict, correlation_id: str) -> dict:
    """Generate a comprehensive Detection Gap Analysis Report.
    
    Compares the agent's action log against SIEM detections to identify
    blind spots in the SOC's detection capabilities.
    """
    action_log = pentest_result.get("action_log", [])
    findings = pentest_result.get("findings", [])
    start_time = pentest_result.get("start_time", "")
    end_time = pentest_result.get("end_time", "")

    # Index all actions and findings to Elasticsearch
    actions_indexed = index_agent_actions(action_log, correlation_id)
    findings_indexed = index_findings_as_alerts(findings, correlation_id, start_time, end_time)

    # Query SIEM for any detections during the pentest window
    siem_detections = query_siem_detections(start_time, end_time, correlation_id)

    # Classify each action
    total_actions = len(action_log)
    successful_actions = len([a for a in action_log if a["success"]])
    detected_count = len(siem_detections)

    # Calculate detection rate
    detection_rate = (detected_count / max(total_actions, 1)) * 100

    # Build the gap report
    report = {
        "report_title": "VANGUARD Cognitive Purple Agent — Detection Gap Analysis",
        "correlation_id": correlation_id,
        "pentest_window": {"start": start_time, "end": end_time},
        "duration_seconds": pentest_result.get("duration_seconds", 0),
        "summary": {
            "total_agent_actions": total_actions,
            "successful_actions": successful_actions,
            "vulnerabilities_found": len(findings),
            "siem_detections": detected_count,
            "detection_rate_percent": round(detection_rate, 1),
            "blind_spots": max(0, total_actions - detected_count),
        },
        "vulnerabilities": findings,
        "siem_detections": siem_detections,
        "agent_action_timeline": [
            {
                "time": a["timestamp"],
                "tool": a["tool"],
                "input": a["input"],
                "detected": False,  # Will be correlated in enhanced version
            }
            for a in action_log
        ],
        "recommendation": _generate_recommendation(detection_rate, findings),
        "elasticsearch_indexed": {
            "telemetry_docs": actions_indexed,
            "alert_docs": findings_indexed,
        }
    }

    return report


def _generate_recommendation(detection_rate: float, findings: list) -> str:
    """Generate a human-readable SOC recommendation based on the gap analysis."""
    if detection_rate >= 80:
        posture = "STRONG"
        detail = "The SOC detected the majority of adversarial actions."
    elif detection_rate >= 40:
        posture = "MODERATE"
        detail = "Significant detection gaps exist in the SIEM pipeline."
    else:
        posture = "CRITICAL"
        detail = "The SOC failed to detect most adversarial actions. Immediate remediation required."

    return (
        f"Security Posture: {posture} ({detection_rate:.0f}% detection rate). "
        f"{detail} "
        f"The autonomous agent discovered {len(findings)} exploitable vulnerabilities. "
        f"Recommendation: Review SIEM correlation rules, enhance logging for HTTP payloads, "
        f"and deploy behavioral analytics to catch multi-step attack chains."
    )


def print_gap_report(report: dict):
    """Pretty-print the gap analysis report to the terminal."""
    print("\n" + "=" * 70)
    print("  📊 DETECTION GAP ANALYSIS REPORT")
    print("=" * 70)
    print(f"  Correlation ID:     {report['correlation_id']}")
    print(f"  Duration:           {report['duration_seconds']:.1f}s")
    print(f"  Agent Actions:      {report['summary']['total_agent_actions']}")
    print(f"  Successful Actions: {report['summary']['successful_actions']}")
    print(f"  Vulns Found:        {report['summary']['vulnerabilities_found']}")
    print(f"  SIEM Detections:    {report['summary']['siem_detections']}")
    print(f"  Detection Rate:     {report['summary']['detection_rate_percent']}%")
    print(f"  SOC Blind Spots:    {report['summary']['blind_spots']}")
    print(f"\n  {'─' * 60}")
    print(f"  VULNERABILITIES DISCOVERED:")
    for i, v in enumerate(report.get("vulnerabilities", []), 1):
        desc = v if isinstance(v, str) else json.dumps(v)
        print(f"    [{i}] {desc[:100]}")
    print(f"\n  {'─' * 60}")
    print(f"  RECOMMENDATION:")
    print(f"    {report.get('recommendation', 'N/A')}")
    print(f"\n  {'─' * 60}")
    print(f"  Elasticsearch:")
    ei = report.get("elasticsearch_indexed", {})
    print(f"    Telemetry indexed: {ei.get('telemetry_docs', 0)} docs")
    print(f"    Alerts indexed:    {ei.get('alert_docs', 0)} docs")
    print("=" * 70)


def get_existing_soc_rules() -> list:
    """Fetch existing SOC detection rules from the vanguard-rules Elasticsearch index."""
    es = get_es()
    if not es:
        print("  ⚠️  Elasticsearch unavailable. Returning empty existing ruleset.")
        return []

    try:
        if not es.indices.exists(index="vanguard-rules"):
            print("  ℹ️  Index 'vanguard-rules' does not exist yet. Will be created on first rule generation.")
            return []
            
        result = es.search(index="vanguard-rules", size=100)
        rules = [hit["_source"] for hit in result["hits"]["hits"]]
        print(f"  ✅ Fetched {len(rules)} existing SOC rules from Elasticsearch.")
        return rules
    except Exception as e:
        logger.error(f"Failed to fetch existing rules from Elasticsearch: {e}")
        return []


def index_soc_rules(rules: list):
    """Save newly generated AI SOC rules into Elasticsearch."""
    es = get_es()
    if not es or not rules:
        print(f"  ⚠️  Skipping ES indexing (es={'connected' if es else 'None'}, rules={len(rules) if rules else 0})")
        return 0

    indexed = 0
    for rule in rules:
        doc = {
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
            "id": rule.get("id", f"SIG-NEW-{indexed}"),
            "rule_name": rule.get("rule_name", rule.get("name", "Unknown Rule")),
            "severity": rule.get("severity", "Medium"),
            "logic": rule.get("logic", "N/A"),
            "source": "vanguard_cognitive_purple_agent"
        }
        try:
            es.index(index="vanguard-rules", document=doc)
            indexed += 1
        except Exception as e:
            logger.error(f"Failed to index generated rule: {e}")
            
    # Force a refresh so they are immediately queryable
    try:
        es.indices.refresh(index="vanguard-rules")
    except:
        pass
        
    return indexed


def generate_soc_rules(action_log: list) -> dict:
    """
    Dynamic Purple Teaming: Review the red team action log, fetch existing rules,
    and automatically generate/index missing Blue Team SOC rules (heuristics/KQL)
    to detect this specific attack chain.
    """
    if not action_log:
        return {"existing_rules": get_existing_soc_rules(), "newly_generated_rules": []}

    existing_rules = get_existing_soc_rules()

    logger.info("Generating dynamic SOC rules based on attack chain...")

    # Format the log for the LLM
    attack_summary = ""
    for idx, a in enumerate(action_log):
        attack_summary += f"Step {idx+1} | Tool: {a['tool']} | Input: {json.dumps(a['input'])}\n"
        if a['success'] and a['output']:
            # Truncate output to keep context window manageable
            safe_output = str(a['output']).replace('\n', ' ')[:100]
            attack_summary += f"   Output preview: {safe_output}...\n"

    system_prompt = """You are an elite Defensive Cybersecurity Analyst and Threat Hunter interacting directly with our SIEM (Elasticsearch).
Your task is to review the attacker's execution log provided by the Red Team and write 2 to 3 realistic SOC Heuristic Rules (e.g., Elasticsearch KQL, Sigma Rules, or Behavioral patterns) that uniquely detect this new attack sequence.

You MUST respond with a valid JSON array of objects.
Do NOT wrap the response in markdown blocks like ```json.
Just output the RAW JSON array.

Strict JSON format required:
[
  {
    "id": "SIG-NEW-001",
    "rule_name": "Short descriptive name",
    "severity": "High/Medium/Critical",
    "logic": "The pseudo-KQL or grep logic"
  }
]
"""

    user_prompt = f"Here is the attack chain logs:\n{attack_summary}\n\nGenerate the JSON array of SOC rules."

    try:
        response = requests.post(
            "http://127.0.0.1:11434/api/generate",
            json={
                "model": "qwen3:8b",
                "prompt": f"/no_think\n{system_prompt}\n\n{user_prompt}",
                "stream": False
            },
            timeout=180
        )
        response.raise_for_status()
        raw_output = response.json().get("response", "[]").strip()
        
        # === DEBUG: Print what the LLM actually returned ===
        print(f"\n{'='*60}")
        print(f"  🔍 RAW LLM OUTPUT FOR SOC RULES:")
        print(f"  {repr(raw_output[:500])}")
        print(f"{'='*60}\n")

        # === CLEAN: Strip <think> tags, markdown wrappers, etc. ===
        raw_output = re.sub(r'<think>.*?</think>', '', raw_output, flags=re.DOTALL).strip()
        raw_output = re.sub(r'^```(?:json)?\s*', '', raw_output)
        raw_output = re.sub(r'\s*```$', '', raw_output)
        raw_output = raw_output.strip()

        # === PARSE: Bulletproof JSON extraction ===
        new_rules = _extract_rules_from_llm(raw_output)
        
        print(f"  ✅ Extracted {len(new_rules)} SOC rules from LLM output.")
        for r in new_rules:
            print(f"     → {r.get('id', '?')}: {r.get('rule_name', '?')} [{r.get('severity', '?')}]")

        # Index the newly generated rules into Elasticsearch
        indexed = index_soc_rules(new_rules)
        print(f"  📥 Indexed {indexed} rules into Elasticsearch.")
        
        return {
            "existing_rules": existing_rules,
            "newly_generated_rules": new_rules
        }
            
    except Exception as e:
        print(f"  ❌ CRITICAL: Failed to generate SOC rules: {e}")
        logger.error(f"Failed to generate SOC rules via Ollama: {e}")

    return {
        "existing_rules": existing_rules,
        "newly_generated_rules": []
    }


def _extract_rules_from_llm(raw_output: str) -> list:
    """
    Bulletproof JSON rule extractor. Handles ALL known Qwen3 output patterns:
      - Direct JSON array: [{...}, {...}]
      - Single dict object: {...}
      - Wrapped in a key: {"rules": [...]} or {"soc_rules": [...]}
      - Deeply nested: {"output": {"rules": [...]}}
      - Empty or malformed responses
    """
    try:
        parsed = json.loads(raw_output)
    except json.JSONDecodeError:
        print(f"  ⚠️  json.loads failed. Attempting regex extraction...")
        # Last resort: try to extract JSON from within the string
        match = re.search(r'\[\s*\{.*\}\s*\]', raw_output, re.DOTALL)
        if match:
            try:
                parsed = json.loads(match.group())
                if isinstance(parsed, list) and len(parsed) > 0:
                    return parsed
            except json.JSONDecodeError:
                pass
        return [{
            "id": "ERR-001",
            "rule_name": "Failed to parse LLM response",
            "severity": "Medium",
            "logic": f"Raw output (truncated): {raw_output[:200]}"
        }]

    # Case 1: Direct array of rules
    if isinstance(parsed, list):
        if len(parsed) > 0:
            return parsed
        return [{
            "id": "ERR-002",
            "rule_name": "LLM returned empty array",
            "severity": "Low",
            "logic": "The AI completed but produced zero rules."
        }]

    # Case 2: It's a dict — need to find the rules inside
    if isinstance(parsed, dict):
        # Case 2a: Single rule object at root level (has rule-like keys)
        if _looks_like_rule(parsed):
            return [parsed]
        
        # Case 2b: Search all values for a list of rule-like dicts
        rules = _find_rules_in_dict(parsed)
        if rules:
            return rules
        
        # Case 2c: Nothing found — return the dict as a single rule anyway
        # (sometimes LLM uses different key names)
        return [{
            "id": parsed.get("id", parsed.get("rule_id", "SIG-AI-001")),
            "rule_name": parsed.get("rule_name", parsed.get("name", parsed.get("title", "AI Generated Rule"))),
            "severity": parsed.get("severity", parsed.get("priority", "Medium")),
            "logic": parsed.get("logic", parsed.get("query", parsed.get("detection", parsed.get("kql", str(parsed)))))
        }]

    return [{
        "id": "ERR-003",
        "rule_name": "Unexpected LLM output type",
        "severity": "Low",
        "logic": f"Got type {type(parsed).__name__}: {str(parsed)[:200]}"
    }]


def _looks_like_rule(d: dict) -> bool:
    """Check if a dict looks like a SOC rule (has common rule keys)."""
    rule_keys = {"id", "rule_name", "name", "title", "severity", "logic", "query", "detection", "kql"}
    return len(set(d.keys()) & rule_keys) >= 2


def _find_rules_in_dict(d: dict) -> list:
    """Recursively search a dict for any list of rule-like dicts."""
    for key, value in d.items():
        if isinstance(value, list) and len(value) > 0:
            if all(isinstance(item, dict) for item in value):
                return value
        elif isinstance(value, dict):
            result = _find_rules_in_dict(value)
            if result:
                return result
    return []
