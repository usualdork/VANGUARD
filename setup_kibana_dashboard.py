"""
VANGUARD SOC - Kibana Dashboard Provisioning Script
Creates Data Views, Saved Searches, and a Dashboard with embedded panels
using the Kibana Saved Objects Import API (NDJSON format).
"""
import requests
import json
import time
import sys

KIBANA_URL = "http://localhost:5601"
HEADERS = {"kbn-xsrf": "true", "Content-Type": "application/json"}

def wait_for_kibana():
    print("[*] Waiting for Kibana to be ready...")
    for i in range(60):
        try:
            r = requests.get(f"{KIBANA_URL}/api/status", timeout=5)
            if r.status_code == 200:
                print("[+] Kibana is ready!")
                return True
        except Exception:
            pass
        time.sleep(2)
    print("[-] Kibana did not become ready in time.")
    return False

def create_data_views():
    print("\n[*] Creating Data Views (Index Patterns)...")
    views = [
        {
            "data_view": {
                "title": "vanguard-telemetry",
                "name": "VANGUARD Telemetry",
                "id": "vanguard-telemetry-dv",
                "timeFieldName": "timestamp"
            }
        },
        {
            "data_view": {
                "title": "vanguard-alerts",
                "name": "VANGUARD Alerts",
                "id": "vanguard-alerts-dv",
                "timeFieldName": "timestamp"
            }
        }
    ]
    for v in views:
        vid = v["data_view"]["id"]
        # Delete existing first
        requests.delete(f"{KIBANA_URL}/api/data_views/data_view/{vid}", headers=HEADERS)
        r = requests.post(f"{KIBANA_URL}/api/data_views/data_view", headers=HEADERS, json=v)
        if r.status_code == 200:
            print(f"  [+] Created: {v['data_view']['name']}")
        else:
            print(f"  [-] Failed: {v['data_view']['name']} -> {r.status_code}: {r.text[:200]}")

def import_dashboard():
    """Use the Kibana Saved Objects Import API with NDJSON to create
    saved searches and a dashboard with embedded panels in one shot."""
    print("\n[*] Building Dashboard with embedded panels...")

    # --- Saved Search for Alerts ---
    alerts_search = {
        "id": "vanguard-alerts-search",
        "type": "search",
        "attributes": {
            "title": "VANGUARD SOC Alerts",
            "description": "All high-severity alerts from the Blue Sensor",
            "columns": ["timestamp", "event_type", "severity", "correlation_id", "ttd_seconds", "description"],
            "sort": [["timestamp", "desc"]],
            "kibanaSavedObjectMeta": {
                "searchSourceJSON": json.dumps({
                    "query": {"query": "", "language": "kuery"},
                    "filter": [],
                    "indexRefName": "kibanaSavedObjectMeta.searchSourceJSON.index"
                })
            }
        },
        "references": [
            {"name": "kibanaSavedObjectMeta.searchSourceJSON.index", "type": "index-pattern", "id": "vanguard-alerts-dv"}
        ]
    }

    # --- Saved Search for Telemetry ---
    telemetry_search = {
        "id": "vanguard-telemetry-search",
        "type": "search",
        "attributes": {
            "title": "VANGUARD Telemetry Logs",
            "description": "All execution telemetry from the Red Node",
            "columns": ["timestamp", "event_type", "correlation_id", "host", "payload_language", "obfuscation"],
            "sort": [["timestamp", "desc"]],
            "kibanaSavedObjectMeta": {
                "searchSourceJSON": json.dumps({
                    "query": {"query": "", "language": "kuery"},
                    "filter": [],
                    "indexRefName": "kibanaSavedObjectMeta.searchSourceJSON.index"
                })
            }
        },
        "references": [
            {"name": "kibanaSavedObjectMeta.searchSourceJSON.index", "type": "index-pattern", "id": "vanguard-telemetry-dv"}
        ]
    }

    # --- Dashboard with two panels ---
    panels_json = json.dumps([
        {
            "version": "8.10.2",
            "type": "search",
            "gridData": {"x": 0, "y": 0, "w": 48, "h": 15, "i": "panel_alerts"},
            "panelIndex": "panel_alerts",
            "embeddableConfig": {
                "enhancements": {},
                "hidePanelTitles": False
            },
            "title": "🚨 SOC Alerts — High Severity Detections",
            "panelRefName": "panel_panel_alerts"
        },
        {
            "version": "8.10.2",
            "type": "search",
            "gridData": {"x": 0, "y": 15, "w": 48, "h": 15, "i": "panel_telemetry"},
            "panelIndex": "panel_telemetry",
            "embeddableConfig": {
                "enhancements": {},
                "hidePanelTitles": False
            },
            "title": "📡 Red Node Execution Telemetry",
            "panelRefName": "panel_panel_telemetry"
        }
    ])

    dashboard = {
        "id": "vanguard-soc-dashboard",
        "type": "dashboard",
        "attributes": {
            "title": "VANGUARD SOC Dashboard",
            "hits": 0,
            "description": "Autonomous Adversarial Simulation — Real-time Attack Telemetry & SOC Alerts",
            "panelsJSON": panels_json,
            "optionsJSON": json.dumps({"useMargins": True, "syncColors": False, "syncCursor": True, "syncTooltips": False, "hidePanelTitles": False}),
            "version": 1,
            "timeRestore": True,
            "timeTo": "now",
            "timeFrom": "now-24h",
            "refreshInterval": {"pause": True, "value": 60000},
            "kibanaSavedObjectMeta": {
                "searchSourceJSON": json.dumps({"query": {"query": "", "language": "kuery"}, "filter": []})
            }
        },
        "references": [
            {"name": "panel_panel_alerts", "type": "search", "id": "vanguard-alerts-search"},
            {"name": "panel_panel_telemetry", "type": "search", "id": "vanguard-telemetry-search"}
        ]
    }

    # Build NDJSON payload (one JSON object per line)
    ndjson_lines = []
    for obj in [alerts_search, telemetry_search, dashboard]:
        ndjson_lines.append(json.dumps(obj))
    ndjson_payload = "\n".join(ndjson_lines) + "\n"

    # Use the import API with overwrite=true
    import_url = f"{KIBANA_URL}/api/saved_objects/_import?overwrite=true"
    import_headers = {"kbn-xsrf": "true"}
    
    r = requests.post(
        import_url,
        headers=import_headers,
        files={"file": ("export.ndjson", ndjson_payload, "application/ndjson")}
    )

    if r.status_code == 200:
        result = r.json()
        if result.get("success"):
            print(f"  [+] Successfully imported {result.get('successCount', 0)} objects!")
        else:
            print(f"  [!] Partial import. Errors: {json.dumps(result.get('errors', []), indent=2)[:500]}")
    else:
        print(f"  [-] Import failed: {r.status_code} -> {r.text[:500]}")

    return r.status_code == 200

def set_default_data_view():
    """Set a default data view so Discover doesn't show the Security alerts pattern."""
    print("\n[*] Setting default Data View to VANGUARD Alerts...")
    r = requests.post(
        f"{KIBANA_URL}/api/data_views/default",
        headers=HEADERS,
        json={"data_view_id": "vanguard-alerts-dv", "force": True}
    )
    if r.status_code == 200:
        print("  [+] Default data view set to VANGUARD Alerts")
    else:
        print(f"  [-] Failed: {r.text[:200]}")

def verify_es_data():
    """Quick check that ES actually has data."""
    print("\n[*] Verifying Elasticsearch data...")
    try:
        for idx in ["vanguard-telemetry", "vanguard-alerts"]:
            r = requests.get(f"http://127.0.0.1:9200/{idx}/_count")
            if r.status_code == 200:
                count = r.json().get("count", 0)
                print(f"  [+] {idx}: {count} documents")
            else:
                print(f"  [-] {idx}: index not found or error")
    except Exception as e:
        print(f"  [-] Cannot reach Elasticsearch: {e}")

if __name__ == "__main__":
    if not wait_for_kibana():
        sys.exit(1)

    verify_es_data()
    create_data_views()
    import_dashboard()
    set_default_data_view()

    dashboard_url = f"{KIBANA_URL}/app/dashboards#/view/vanguard-soc-dashboard?_g=(time:(from:now-24h,to:now))"
    discover_url = f"{KIBANA_URL}/app/discover#/?_a=(index:'vanguard-alerts-dv')&_g=(time:(from:now-24h,to:now))"

    print("\n" + "=" * 60)
    print("  VANGUARD SOC SETUP COMPLETE")
    print("=" * 60)
    print(f"\n  Dashboard URL:\n  {dashboard_url}")
    print(f"\n  Discover (Alerts) URL:\n  {discover_url}")
    print(f"\n  ⚠️  Make sure to set the time range to 'Last 24 hours'")
    print("=" * 60)
