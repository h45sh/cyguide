import html
import json
import re
from datetime import datetime, UTC
from typing import Dict, Any, List
from cyguide.engine.store import GraphStore

def build_markdown_table_for_type(schema_type: str, nodes: List[Dict[str, Any]]) -> List[str]:
    """Dynamically construct a clean Markdown table with columns for all unique keys present in the nodes."""
    parsed_nodes = []
    all_keys = set()
    
    for n in nodes:
        try:
            pik = json.loads(n.get("pik_json") or "{}")
        except Exception:
            pik = {}
        try:
            data = json.loads(n.get("data_json") or "{}")
        except Exception:
            data = {}
            
        merged = {}
        # Merge PIK and data attributes
        for k, v in pik.items():
            if v is not None and v != "":
                merged[k] = v
        for k, v in data.items():
            if v is not None and v != "":
                merged[k] = v
                
        # Clean suggestion metadata to keep the tables focused on real evidence
        for k in ["tool_suggestion", "recommended_command"]:
            merged.pop(k, None)
            
        # Record standard entity columns
        merged["ID"] = n["id"][:8]
        merged["Status"] = n.get("status", "confirmed").upper()
        
        if merged:
            parsed_nodes.append(merged)
            all_keys.update(merged.keys())
        
    if not parsed_nodes or not all_keys:
        return ["*No detailed properties recorded.*"]
        
    # Column order priority list (important headers show first)
    important_keys = ["ID", "ip", "host_ip", "domain", "url", "port", "protocol", "service_name", "vuln_type", "vuln_id", "severity", "username", "password", "Status"]
    
    columns = []
    for k in important_keys:
        if k in all_keys:
            columns.append(k)
            all_keys.remove(k)
            
    # Alphabetical sort for all other dynamically discovered fields
    columns.extend(sorted(list(all_keys)))
    
    # Header line
    header_labels = [col.replace("_", " ").title() for col in columns]
    lines = []
    lines.append("| " + " | ".join(header_labels) + " |")
    lines.append("| " + " | ".join([":---" for _ in columns]) + " |")
    
    # Data rows
    for node in parsed_nodes:
        row_values = []
        for col in columns:
            val = node.get(col, "-")
            if isinstance(val, (dict, list)):
                val = json.dumps(val)
            val_str = html.escape(str(val)).replace("|", "\\|").replace("\r\n", " ").replace("\n", " ")
            row_values.append(val_str)
        lines.append("| " + " | ".join(row_values) + " |")
        
    return lines

async def generate_markdown_report(store: GraphStore, session_id: str) -> str:
    """Generate a structured Markdown report summarizing findings and logs for a session."""
    session = await store.get_session(session_id)
    if not session:
        return "# Session Not Found\n"
        
    workspace = await store.get_workspace(session["workspace_id"])
    workspace_name = workspace["name"] if workspace else "Unknown Workspace"
    
    stats = await store.get_stats(session_id)
    nodes = await store.get_all_nodes(session_id)
    edges = await store.get_all_edges(session_id)
    events = await store.get_event_log(session_id)
    
    report = []
    
    # 1. Title & Metadata
    report.append(f"# CyGuide Investigation Report: {session['name']}")
    report.append("")
    report.append("## 📋 Session Overview")
    report.append(f"- **Session Name**: {session['name']}")
    report.append(f"- **Workspace**: {workspace_name}")
    report.append(f"- **Status**: {session['status']}")
    report.append(f"- **Created At**: {session['created_at']}")
    report.append(f"- **Report Generated At**: {datetime.now(UTC).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    report.append("")
    
    # 2. Summary Metrics
    report.append("### 📊 Metrics Summary")
    report.append(f"- **Total Discovered Entities**: {stats.get('total', 0)}")
    for schema, count in sorted(stats.items()):
        if schema == "total":
            continue
        report.append(f"  - **{schema}**: {count}")
    report.append("")
    
    # 3. Discovered Entities Details
    report.append("## 🔍 Discovered Entities")
    report.append("")
    
    nodes_by_type: Dict[str, List[Dict[str, Any]]] = {}
    for n in nodes:
        nodes_by_type.setdefault(n["schema_type"], []).append(n)
        
    for schema_type, type_nodes in sorted(nodes_by_type.items()):
        report.append(f"### `{schema_type}`")
        report.append("")
        
        table_lines = build_markdown_table_for_type(schema_type, type_nodes)
        report.extend(table_lines)
        report.append("")
        
    # 4. Relationships Mermaid Graph
    if edges:
        report.append("## 🔗 Entity Relationships (Mermaid Graph)")
        report.append("")
        report.append("```mermaid")
        report.append("graph TD")
        
        id_labels = {}
        for n in nodes:
            st = n["schema_type"]
            pik = json.loads(n["pik_json"])
            if st == "network.host":
                lbl = pik.get("ip") or pik.get("host_ip") or n["id"][:8]
            elif st == "network.service":
                lbl = f"{pik.get('port')}/{pik.get('protocol', 'tcp')}"
            elif st.startswith("web."):
                lbl = pik.get("url") or pik.get("path") or n["id"][:8]
            else:
                lbl = n["id"][:8]
            
            # Clean label of quotes/brackets for Mermaid safety
            lbl_clean = str(lbl).replace('"', '\\"').replace('[', '(').replace(']', ')')
            id_labels[n["id"]] = f'{n["id"][:8]}["{lbl_clean}"]'
            
        for edge in edges:
            src = edge["source_id"]
            dst = edge["target_id"]
            rel = edge["relation_type"]
            if src in id_labels and dst in id_labels:
                report.append(f"  {id_labels[src]} -- {rel} --> {id_labels[dst]}")
                
        report.append("```")
        report.append("")

    # 5. Event Logs & Tool History
    report.append("## 🪵 Tool Execution History")
    report.append("")
    
    tool_events = [ev for ev in events if ev.get("schema_type") == "system.event"]
    
    if not tool_events:
        report.append("No tools were run in this session.")
    else:
        for idx, ev in enumerate(tool_events, 1):
            try:
                action_payload = json.loads(ev.get("action_payload") or "{}")
            except Exception:
                action_payload = {}
            try:
                result_payload = json.loads(ev.get("result_payload") or "{}")
            except Exception:
                result_payload = {}
                
            tool_name = action_payload.get("tool_name", "Unknown Tool")
            params = action_payload.get("params", {})
            raw_flags = params.get("raw_flags", "")
            
            status = "FAILED" if "error" in result_payload and result_payload["error"] else "DONE"
            if result_payload.get("error") == "Terminated manually":
                status = "TERMINATED"
                
            report.append(f"### {idx}. {tool_name} (Status: {status})")
            report.append(f"- **Timestamp**: {ev.get('timestamp')}")
            cmd_full = f"{tool_name} {raw_flags}".strip()
            report.append(f"- **Command**: `{cmd_full}`")
            
            if "error" in result_payload and result_payload["error"]:
                report.append(f"- **Error**: {result_payload['error']}")
            report.append("")
            
            output = result_payload.get("output", "").strip()
            if output:
                longest = max((len(m) for m in re.findall(r"`+", output)), default=0)
                fence = "`" * max(3, longest + 1)
                report.append("<details>")
                report.append("<summary>Raw Command Output</summary>")
                report.append("")
                report.append(f"{fence}text")
                report.append(output)
                report.append(fence)
                report.append("</details>")
            else:
                report.append("*No output recorded.*")
            report.append("")
            report.append("---")
            report.append("")
            
    return "\n".join(report)
