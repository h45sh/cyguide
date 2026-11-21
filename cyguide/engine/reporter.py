"""Deep module managing forensic report compilation, markdown formatting, and export."""

import html
import json
import os
import re
from datetime import UTC, datetime
from typing import Any, Dict, List, Optional

from cyguide.engine.store import GraphStore


class SessionReportService:
    """The deep module managing forensic investigation reporting, Markdown table

    synthesis, Mermaid graph visualization, and secure file export.
    """

    def __init__(self, store: Optional[GraphStore] = None):
        self.store = store

    @staticmethod
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

        if not parsed_nodes or not all_keys:
            return ["*No detailed properties recorded.*"]

        important_keys = [
            "ID",
            "ip",
            "host_ip",
            "domain",
            "url",
            "port",
            "protocol",
            "service_name",
            "vuln_type",
            "vuln_id",
            "severity",
            "username",
            "password",
            "Status",
        ]

        columns = []
        for k in important_keys:
            if k in all_keys:
                columns.append(k)
                all_keys.remove(k)

        columns.extend(sorted(list(all_keys)))

        header_labels = [col.replace("_", " ").title() for col in columns]
        lines = []
        lines.append("| " + " | ".join(header_labels) + " |")
        lines.append("| " + " | ".join([":---" for _ in columns]) + " |")

        for node in parsed_nodes:
            row_values = []
            for col in columns:
                val = node.get(col, "-")
                if isinstance(val, (dict, list)):
                    val = json.dumps(val)
                val_str = (
                    html.escape(str(val))
                    .replace("|", "\\|")
                    .replace("\r\n", " ")
                    .replace("\n", " ")
                )
                row_values.append(val_str)
            lines.append("| " + " | ".join(row_values) + " |")

        return lines

    def render_markdown(self, data: Dict[str, Any]) -> str:
        """Pure in-memory Markdown report generator from a structured session data bundle."""
        session = data.get("session") or {}
        workspace_name = data.get("workspace_name") or "Unknown Workspace"
        stats = data.get("stats") or {}
        nodes = data.get("nodes") or []
        edges = data.get("edges") or []
        events = data.get("events") or []

        session_name = session.get("name", "Unknown Session")
        session_status = session.get("status", "unknown")
        session_created = session.get("created_at", "unknown")

        report = []

        # 1. Title & Metadata
        report.append(f"# CyGuide Investigation Report: {session_name}")
        report.append("")
        report.append("## Session Overview")
        report.append(f"- **Session Name**: {session_name}")
        report.append(f"- **Workspace**: {workspace_name}")
        report.append(f"- **Status**: {session_status}")
        report.append(f"- **Created At**: {session_created}")
        report.append(
            f"- **Report Generated At**: {datetime.now(UTC).strftime('%Y-%m-%d %H:%M:%S UTC')}"
        )
        report.append("")

        # 2. Summary Metrics
        report.append("### Metrics Summary")
        report.append(f"- **Total Discovered Entities**: {stats.get('total', 0)}")
        for schema, count in sorted(stats.items()):
            if schema == "total":
                continue
            report.append(f"  - **{schema}**: {count}")
        report.append("")

        # 3. Discovered Entities Details
        report.append("## Discovered Entities")
        report.append("")

        nodes_by_type: Dict[str, List[Dict[str, Any]]] = {}
        for n in nodes:
            nodes_by_type.setdefault(n["schema_type"], []).append(n)

        for schema_type, type_nodes in sorted(nodes_by_type.items()):
            report.append(f"### `{schema_type}`")
            report.append("")

            table_lines = self.build_markdown_table_for_type(schema_type, type_nodes)
            report.extend(table_lines)
            report.append("")

        # 4. Relationships Mermaid Graph
        if edges:
            report.append("## Entity Relationships (Mermaid Graph)")
            report.append("")
            report.append("```mermaid")
            report.append("graph TD")

            id_labels = {}
            for n in nodes:
                st = n["schema_type"]
                try:
                    pik = json.loads(n.get("pik_json") or "{}")
                except Exception:
                    pik = {}
                if st == "network.host":
                    lbl = pik.get("ip") or pik.get("host_ip") or n["id"][:8]
                elif st == "network.service":
                    lbl = f"{pik.get('port')}/{pik.get('protocol', 'tcp')}"
                elif st.startswith("web."):
                    lbl = pik.get("url") or pik.get("path") or n["id"][:8]
                else:
                    lbl = n["id"][:8]

                lbl_clean = str(lbl).replace('"', '\\"').replace("[", "(").replace("]", ")")
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
        report.append("## Tool Execution History")
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

                status = (
                    "FAILED" if "error" in result_payload and result_payload["error"] else "DONE"
                )
                if result_payload.get("error") == "Terminated manually":
                    status = "TERMINATED"

                report.append(f"### {idx}. {tool_name} (Status: {status})")
                report.append(f"- **Timestamp**: {ev.get('timestamp')}")
                cmd_full = f"{tool_name} {raw_flags}".strip()
                cmd_code = f"`` {cmd_full} ``" if "`" in cmd_full else f"`{cmd_full}`"
                report.append(f"- **Command**: {cmd_code}")

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

    async def fetch_report_data(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Fetch structured session audit, graph, and entity metrics for reporting."""
        if not self.store:
            raise ValueError("SessionReportService requires a configured GraphStore.")

        session = await self.store.get_session(session_id)
        if not session:
            return None

        workspace = await self.store.get_workspace(session["workspace_id"])
        workspace_name = workspace["name"] if workspace else "Unknown Workspace"

        stats = await self.store.get_stats(session_id)
        nodes = await self.store.get_all_nodes(session_id)
        edges = await self.store.get_all_edges(session_id)
        events = await self.store.get_event_log(session_id)

        return {
            "session": session,
            "workspace_name": workspace_name,
            "stats": stats,
            "nodes": nodes,
            "edges": edges,
            "events": events,
        }

    async def generate_markdown_report(self, session_id: str) -> str:
        """Generate a structured Markdown report summarizing findings and logs for a session."""
        data = await self.fetch_report_data(session_id)
        if not data:
            return "# Session Not Found\n"
        return self.render_markdown(data)

    @staticmethod
    def export_text_file(content: str, output_path: str) -> None:
        """Atomically write text content to a destination file with 0o600 permissions."""
        out_dir = os.path.dirname(os.path.abspath(output_path))
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)
        fd = os.open(output_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        try:
            with open(fd, "w", encoding="utf-8", closefd=False) as f:
                f.write(content)
        finally:
            os.close(fd)
        try:
            os.chmod(output_path, 0o600)
        except OSError:
            pass

    async def export_markdown_report(self, session_id: str, output_path: str) -> None:
        """Generate and write a structured Markdown report to a destination file with atomic 0o600 permissions."""
        content = await self.generate_markdown_report(session_id)
        self.export_text_file(content, output_path)

    @staticmethod
    def extract_structured_findings_summary(nodes: List[Dict[str, Any]]) -> tuple[str, str]:
        """Format both a human-readable UI card summary and a dense LLM context block from raw finding nodes."""
        if not nodes:
            return "*No structured findings in current session yet.*", "None"

        services = []
        hosts = []
        endpoints = []
        dns_records = []
        vulns = []

        for n in nodes:
            st = n.get("schema_type", "")
            pik_raw = n.get("pik_json", "{}")
            pik = json.loads(pik_raw) if isinstance(pik_raw, str) else (pik_raw or {})
            data_raw = n.get("data_json", "{}")
            data = json.loads(data_raw) if isinstance(data_raw, str) else (data_raw or {})

            if st == "network.service":
                port = pik.get("port")
                proto = pik.get("protocol", "tcp")
                svc = data.get("service_name") or data.get("product") or "unknown"
                ver = data.get("version", "")
                ver_str = f" {ver}" if ver else ""
                services.append(f"Port `{port}/{proto}`: {svc}{ver_str}")
            elif st == "network.host":
                ip = pik.get("ip") or pik.get("host_ip")
                status = data.get("state") or n.get("status") or "up"
                hosts.append(f"`{ip}` (State: {status})")
            elif st.startswith("web."):
                url = pik.get("url") or pik.get("path")
                code = data.get("status_code", "")
                code_str = f" [Status: {code}]" if code else ""
                endpoints.append(f"`{url}`{code_str}")
            elif st in ("domain.info", "dns.record"):
                dom = pik.get("domain")
                rtype = pik.get("type", "A")
                val = pik.get("value", "")
                val_str = f" ❯ {val}" if val and val not in ("ANY", "unknown") else ""
                dns_records.append(f"`{dom}` [{rtype}{val_str}]")
            elif st.startswith("vulnerability."):
                vid = pik.get("vuln_id") or pik.get("cve_id") or pik.get("title")
                sev = data.get("severity", "info").upper()
                vulns.append(f"[{sev}] `{vid}`")

        ui_sections = []
        llm_sections = []

        if hosts:
            ui_sections.append(
                f"**Hosts ({len(hosts)})**:\n"
                + "\n".join(f"- {h}" for h in hosts[:6])
                + (f"\n- *...and {len(hosts) - 6} more hosts*" if len(hosts) > 6 else "")
            )
            llm_sections.append(f"Hosts ({len(hosts)}): " + ", ".join(hosts[:10]))

        if services:
            ui_sections.append(
                f"**Services ({len(services)})**:\n"
                + "\n".join(f"- {s}" for s in services[:8])
                + (f"\n- *...and {len(services) - 8} more services*" if len(services) > 8 else "")
            )
            llm_sections.append(f"Services ({len(services)}): " + "; ".join(services[:12]))

        if endpoints:
            ui_sections.append(
                f"**Web Endpoints ({len(endpoints)})**:\n"
                + "\n".join(f"- {e}" for e in endpoints[:6])
                + (
                    f"\n- *...and {len(endpoints) - 6} more endpoints*"
                    if len(endpoints) > 6
                    else ""
                )
            )
            llm_sections.append(f"Web Endpoints ({len(endpoints)}): " + ", ".join(endpoints[:10]))

        if vulns:
            ui_sections.append(
                f"**Vulnerabilities ({len(vulns)})**:\n"
                + "\n".join(f"- {v}" for v in vulns[:6])
                + (f"\n- *...and {len(vulns) - 6} more*" if len(vulns) > 6 else "")
            )
            llm_sections.append(f"Vulnerabilities ({len(vulns)}): " + "; ".join(vulns[:10]))

        if dns_records:
            ui_sections.append(
                f"**DNS Records ({len(dns_records)})**:\n"
                + "\n".join(f"- {d}" for d in dns_records[:5])
                + (
                    f"\n- *...and {len(dns_records) - 5} more records*"
                    if len(dns_records) > 5
                    else ""
                )
            )
            llm_sections.append(f"DNS Records ({len(dns_records)}): " + ", ".join(dns_records[:8]))

        ui_text = (
            "\n\n".join(ui_sections)
            if ui_sections
            else "*No structured findings in current session yet.*"
        )
        llm_text = "\n".join(llm_sections) if llm_sections else "None"
        return ui_text, llm_text

    async def extract_structured_findings(self, session_id: str) -> tuple[str, str]:
        """Fetch session nodes from store and format UI and LLM structured finding summaries."""
        if not self.store:
            return "*No structured findings in current session yet.*", "None"
        try:
            if hasattr(self.store, "get_all_nodes"):
                nodes = await self.store.get_all_nodes(str(session_id))
            elif hasattr(self.store, "list_nodes"):
                nodes = await self.store.list_nodes(str(session_id))
            else:
                nodes = []
        except Exception:
            nodes = []
        return self.extract_structured_findings_summary(nodes)
