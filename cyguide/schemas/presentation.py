"""Presentation helpers and display mapping for finding schemas and graph nodes.

Keeps UI screens and widgets purely declarative by encapsulating schema-specific
labeling, bullet symbols, colors, and human-readable activity formatting.
"""

import json
from typing import Any, Dict, List, Optional, Tuple

__all__ = [
    "SCHEMA_DISPLAY_MAP",
    "get_schema_display_meta",
    "format_activity_entry",
    "format_node_label",
    "build_ip_to_name_map",
]

# schema_type: (bullet_symbol, color_hex, display_name)
SCHEMA_DISPLAY_MAP: Dict[str, Tuple[str, str, str]] = {
    "network.host": ("●", "#38bdf8", "Hosts"),
    "network.service": ("●", "#34d399", "Services"),
    "network.netblock": ("●", "#a78bfa", "Netblocks"),
    "web.endpoint": ("●", "#f59e0b", "Web Endpoints"),
    "web.resource": ("●", "#fbbf24", "Web Resources"),
    "web.vulnerability": ("▲", "#f87171", "Web Vulnerabilities"),
    "web.technology": ("●", "#06b6d4", "Technologies"),
    "vulnerability.found": ("▲", "#f87171", "Vulnerabilities"),
    "exploit.reference": ("▲", "#f43f5e", "Exploits"),
    "audit.misconfig": ("▲", "#fb923c", "Misconfigurations"),
    "domain.info": ("●", "#ec4899", "Domains"),
    "dns.record": ("●", "#60a5fa", "DNS Records"),
    "tls.certificate": ("●", "#2dd4bf", "TLS Certificates"),
    "credential.found": ("◆", "#fbbf24", "Credentials"),
    "process.running": ("●", "#4ade80", "Processes"),
    "file.system_object": ("●", "#94a3b8", "Files"),
    "software.package": ("●", "#818cf8", "Packages"),
    "entity.alias": ("●", "#c084fc", "Aliases"),
}


def get_schema_display_meta(schema_type: str) -> Tuple[str, str, str]:
    """Return (bullet_symbol, color_hex, display_name) for a schema type."""
    if schema_type in SCHEMA_DISPLAY_MAP:
        return SCHEMA_DISPLAY_MAP[schema_type]
    clean_name = (
        schema_type.split(".")[-1].replace("_", " ").title()
        if "." in schema_type
        else schema_type.replace("_", " ").title()
    )
    return ("◆", "#94a3b8", clean_name)


def format_activity_entry(
    session_name: str,
    schema_type: str,
    human_readable: str,
    finding_json: Optional[str] = None,
    finding_obj: Optional[Any] = None,
) -> str:
    """Format an activity log entry into a concise human-readable dashboard label."""
    s_name = session_name
    if s_name.startswith("Session "):
        s_name = s_name[8:]
    if len(s_name) > 10:
        s_name = s_name[:8] + ".."

    message = human_readable
    if schema_type != "system.event":
        try:
            if finding_obj:
                pik = getattr(finding_obj, "pik", {})
                data = getattr(finding_obj, "data", {})
            else:
                finding_data = json.loads(finding_json) if finding_json else {}
                pik = finding_data.get("pik", {})
                data = finding_data.get("data", {})

            if schema_type == "network.host" and "ip" in pik:
                message = f"Host: {pik['ip']}"
            elif schema_type == "network.service" and "port" in pik:
                service_name = data.get("service_name") or pik.get("service") or "unknown"
                message = f"Port: {pik['port']} ({service_name})"
            elif "cidr" in pik:
                message = f"Netblock: {pik['cidr']}"
            elif "vuln_type" in pik:
                message = f"Vuln: {pik['vuln_type']}"
            elif "vuln_id" in pik:
                message = f"Vuln: {pik['vuln_id']}"
            elif "exploit_id" in pik:
                message = f"Exploit: {pik['exploit_id']}"
            elif "technology_name" in pik:
                version = data.get("version")
                tech = pik["technology_name"]
                message = f"Tech: {tech} {version}" if version else f"Tech: {tech}"
            elif "check_id" in pik:
                message = f"Misconfig: {pik['check_id']}"
            elif "url" in pik:
                url = pik["url"]
                if url.startswith("http://"):
                    url = url[7:]
                elif url.startswith("https://"):
                    url = url[8:]
                message = f"URL: {url}"
            elif "domain" in pik:
                message = f"Domain: {pik['domain']}"
            elif "endpoint" in pik:
                message = f"Endpoint: {pik['endpoint']}"
            else:
                short_type = schema_type.split(".")[-1] if "." in schema_type else schema_type
                message = f"New {short_type}"
        except Exception:
            pass

    if message.startswith("Ran "):
        message = f"Run: {message[4:]}"

    return f"[{s_name}] {message}"


def build_ip_to_name_map(nodes: List[Dict[str, Any]]) -> Dict[str, str]:
    """Scan finding nodes to map IP addresses to known hostnames or domains."""
    ip_to_name: Dict[str, str] = {}
    for n in nodes:
        st = n.get("schema_type", "")
        try:
            npik = json.loads(n.get("pik_json", "{}"))
            ndata = json.loads(n.get("data_json", "{}"))
        except Exception:
            continue

        if st == "network.host":
            ip_val = npik.get("ip") or npik.get("host_ip")
            if ip_val:
                if ndata.get("alias"):
                    ip_to_name[ip_val] = ndata["alias"]
                elif ndata.get("hostname"):
                    ip_to_name[ip_val] = ndata["hostname"]
                elif ip_val in ("127.0.0.1", "::1"):
                    ip_to_name.setdefault(ip_val, "localhost")

        elif st == "dns.record":
            dom = npik.get("domain")
            val = npik.get("value")
            if dom and val and val not in ("ANY", "unknown") and "." in val:
                ip_to_name.setdefault(val, dom)

        elif st == "domain.info":
            dom = npik.get("domain")
            ip = ndata.get("ip") or ndata.get("resolved_ip")
            if dom and ip:
                ip_to_name.setdefault(ip, dom)

    return ip_to_name


def format_node_label(node: Dict[str, Any], ip_to_name: Optional[Dict[str, str]] = None) -> str:
    """Resolve a clean, human-readable display label for a graph node."""
    ip_map = ip_to_name or {}
    st = node.get("schema_type", "")
    try:
        pik = json.loads(node.get("pik_json", "{}"))
        data = json.loads(node.get("data_json", "{}"))
    except Exception:
        return str(node.get("id", ""))[:8]

    custom_alias = data.get("alias")

    if st == "network.host":
        ip = pik.get("ip") or pik.get("host_ip") or str(node.get("id", ""))[:8]
        hostname = custom_alias or data.get("hostname") or ip_map.get(ip)
        if ip in ("127.0.0.1", "::1") and not hostname:
            hostname = "localhost"
        if hostname:
            return f"{ip} ({hostname})"
        return str(ip)
    elif st == "network.service":
        port = pik.get("port")
        protocol = pik.get("protocol", "tcp")
        base = f"{port}/{protocol}" if port else str(node.get("id", ""))[:8]
        return f"{base} ({custom_alias})" if custom_alias else base
    elif st == "network.netblock":
        cidr = pik.get("cidr") or "Netblock"
        org = custom_alias or data.get("organization")
        if org and len(org) > 16:
            org = org[:14] + "…"
        return f"{cidr} ({org})" if org else str(cidr)
    elif st == "domain.info":
        dom = pik.get("domain", "Domain")
        reg = custom_alias or data.get("registrar") or data.get("organization")
        if reg and len(reg) > 16:
            reg = reg[:14] + "…"
        return f"{dom} ({reg})" if reg else str(dom)
    elif st == "dns.record":
        dom = pik.get("domain", "")
        rtype = pik.get("type", "DNS")
        val = pik.get("value", "")
        base = (
            f"{dom} [{rtype} ❯ {val}]"
            if (val and val not in ("ANY", "unknown"))
            else f"{dom} [{rtype}]"
        )
        return f"{base} ({custom_alias})" if custom_alias else base
    elif st == "tls.certificate":
        cn = custom_alias or data.get("common_name")
        return (
            f"TLS: {cn}"
            if cn
            else f"TLS: {pik.get('fingerprint_sha256', str(node.get('id', ''))[:8])[:16]}"
        )
    elif st == "exploit.reference":
        eid = pik.get("exploit_id", "Exploit")
        title = data.get("title")
        base = (
            f"{eid}: {title[:32]}…"
            if (title and len(title) > 32)
            else f"{eid}: {title}"
            if title
            else str(eid)
        )
        return f"{base} ({custom_alias})" if custom_alias else base
    elif st == "web.technology":
        tech = pik.get("technology_name", "Technology")
        ver = data.get("version")
        base = f"{tech} {ver}" if ver else tech
        return f"{base} ({custom_alias})" if custom_alias else base
    elif st == "audit.misconfig":
        cid = pik.get("check_id", "Misconfig")
        title = data.get("title")
        sev = data.get("severity", "").upper()
        base = f"[{sev}] {cid}" if sev else cid
        return f"{base} ({custom_alias})" if custom_alias else base
    elif st.startswith("web."):
        base = pik.get("url") or pik.get("path") or f"{str(node.get('id', ''))[:8]}"
        return f"{base} ({custom_alias})" if custom_alias else str(base)
    elif st.startswith("credential."):
        username = pik.get("username", "?")
        base = f"{username}:****"
        return f"{base} ({custom_alias})" if custom_alias else str(base)
    elif st.startswith("vulnerability."):
        base = (
            pik.get("vuln_id")
            or pik.get("cve_id")
            or pik.get("title")
            or str(node.get("id", ""))[:8]
        )
        return f"{base} ({custom_alias})" if custom_alias else str(base)
    else:
        base = str(node.get("id", ""))[:8]
        return f"{base} ({custom_alias})" if custom_alias else str(base)
