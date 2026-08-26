"""Recommendation Engine for suggesting tools based on discovered findings."""

import os
import json
import logging
from typing import List, Dict, Any
from cyguide.schemas.base import BaseFinding
from cyguide.schemas.web import WebEndpoint, WebVulnerability
from cyguide.schemas.dns import DnsRecord, DomainInfo
from cyguide.engine.store import GraphStore

logger = logging.getLogger(__name__)


class RecommendationRule:
    """Base class for declarative recommendation rules."""
    def evaluate(self, session_id: str, finding: BaseFinding, store: GraphStore) -> List[BaseFinding]:
        raise NotImplementedError


class WebServiceRecommendationRule(RecommendationRule):
    """If a port 80/443/8080 service is found, recommend running gobuster."""
    def evaluate(self, session_id: str, finding: BaseFinding, store: GraphStore) -> List[BaseFinding]:
        if finding.schema_type != "network.service":
            return []

        port = finding.pik.get("port")
        service_name = finding.data.get("service_name", "").lower()
        host_ip = finding.pik.get("host_ip")

        if not host_ip or not port:
            return []

        # If it's a web service
        if port in (80, 443, 8080) or "http" in service_name:
            scheme = "https" if port == 443 else "http"
            url = f"{scheme}://{host_ip}:{port}/"
            if port == 80 and scheme == "http":
                url = f"http://{host_ip}/"
            elif port == 443 and scheme == "https":
                url = f"https://{host_ip}/"

            proposed_endpoint = WebEndpoint.create(
                url=url,
                host_ip=host_ip,
                port=port
            )
            proposed_endpoint.status = "proposed"
            # Attach metadata for command resolution in TUI
            proposed_endpoint.data["tool_suggestion"] = "gobuster"
            proposed_endpoint.data["recommended_command"] = f"gobuster dir -u {url} -w {{wordlist}}"
            
            return [proposed_endpoint]

        return []


class WebVulnerabilityRecommendationRule(RecommendationRule):
    """If a confirmed web endpoint is found, suggest scanning it for vulnerabilities with nikto."""
    def evaluate(self, session_id: str, finding: BaseFinding, store: GraphStore) -> List[BaseFinding]:
        if finding.schema_type != "web.endpoint":
            return []

        url = finding.pik.get("url")
        if not url:
            return []

        # Propose a vulnerability scan recommendation
        proposed_vuln = WebVulnerability.create(
            url=url,
            vuln_type="security_audit",
            parameter=""
        )
        proposed_vuln.status = "proposed"
        proposed_vuln.data["tool_suggestion"] = "nikto"
        proposed_vuln.data["recommended_command"] = f"nikto -h {url}"
        proposed_vuln.data["description"] = f"Scan web endpoint {url} for vulnerabilities using nikto"

        return [proposed_vuln]


class SubdomainRecommendationRule(RecommendationRule):
    """If a host has a hostname/domain, suggest subfinder subdomain discovery."""
    def evaluate(self, session_id: str, finding: BaseFinding, store: GraphStore) -> List[BaseFinding]:
        if finding.schema_type != "network.host":
            return []

        hostname = finding.data.get("hostname")
        if not hostname:
            return []

        # Check if the hostname looks like a domain name (contains letters, dots, and is not an IP)
        is_ip = True
        try:
            import socket
            socket.inet_aton(hostname)
        except (socket.error, OSError):
            is_ip = False

        if is_ip or "." not in hostname:
            return []

        # Find top level domain or domain name
        domain = hostname
        proposed_record = DnsRecord.create(
            domain=domain,
            record_type="A",
            value="ENUM_SUGGESTION",
            resolved_ip=finding.pik.get("ip")
        )
        proposed_record.status = "proposed"
        proposed_record.data["tool_suggestion"] = "subfinder"
        proposed_record.data["recommended_command"] = f"subfinder -d {domain}"
        
        return [proposed_record]


class WhoisRecommendationRule(RecommendationRule):
    """If a host has a public IP/hostname, suggest whois registration lookup."""
    def evaluate(self, session_id: str, finding: BaseFinding, store: GraphStore) -> List[BaseFinding]:
        if finding.schema_type != "network.host":
            return []

        ip = finding.pik.get("ip")
        if not ip:
            return []

        # Filter out private IPs
        parts = ip.split(".")
        if len(parts) == 4:
            try:
                p1, p2 = int(parts[0]), int(parts[1])
                # Private IP ranges: 10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16, 127.0.0.0/8
                if p1 == 10 or p1 == 127:
                    return []
                if p1 == 172 and (16 <= p2 <= 31):
                    return []
                if p1 == 192 and p2 == 168:
                    return []
            except ValueError:
                return []

        proposed_info = DomainInfo.create(
            domain=ip,
            registrar="WHOIS_LOOKUP",
            organization="WHOIS_LOOKUP"
        )
        proposed_info.status = "proposed"
        proposed_info.data["tool_suggestion"] = "whois"
        proposed_info.data["recommended_command"] = f"whois {ip}"

        return [proposed_info]


class RecommendationEngine:
    """Evaluates findings reactively and persists proposed findings in the database."""

    def __init__(self, store: GraphStore):
        self.store = store
        self.rules: List[RecommendationRule] = [
            WebServiceRecommendationRule(),
            WebVulnerabilityRecommendationRule(),
            SubdomainRecommendationRule(),
            WhoisRecommendationRule(),
        ]

    async def handle_upsert(self, session_id: str, finding: BaseFinding) -> None:
        """Triggered reactively when a finding is saved to the store."""
        # Only evaluate recommendations based on CONFIRMED findings
        if finding.status != "confirmed":
            return

        for rule in self.rules:
            try:
                proposed_findings = rule.evaluate(session_id, finding, self.store)
                for proposed in proposed_findings:
                    # Check if the node already exists in database (either confirmed or proposed)
                    node_id = self.store._generate_node_id(proposed.schema_type, proposed.pik)
                    existing = await self.store.get_node(session_id, node_id)
                    if not existing:
                        logger.info(f"Proposing finding {proposed.schema_type} for session {session_id}")
                        await self.store.upsert_finding(session_id, proposed)
            except Exception as e:
                logger.error(f"Error in recommendation rule {rule.__class__.__name__}: {e}")
