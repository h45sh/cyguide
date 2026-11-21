"""Deep module for pre-flight dependency, asset, and parameter verification.

Enforces fail-fast validation before tool execution in Learning and Power modes:
1. Binary Discovery: Validates binary existence in PATH with OS-specific install hints.
2. Wordlist Verification: Inspects referenced macros/paths and offers auto-seeding.
3. Target Validation: Detects empty targets, unresolved variables, and URL scheme mismatches.
4. Security Gating: Enforces SSRF link-local metadata protection and sudo command bans.
5. One-Click Remediation: Provides automated actions to fix detected issues instantly.
"""

from __future__ import annotations

import os
import re
import shutil
import urllib.parse
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, List, Literal, Optional, Set, Tuple

from cyguide import paths
from cyguide.engine.diagnostics import INSTALLATION_HINTS
from cyguide.engine.gateway import is_blocked_destination
from cyguide.engine.wordlists import (
    DEFAULT_WORDLIST_NAME,
    WORDLIST_MACRO_REGEX,
    seed_bundled_wordlists,
)

WEB_TOOLS: Set[str] = {"gobuster", "ffuf", "nikto", "nuclei", "sqlmap"}
NETWORK_TOOLS: Set[str] = {"nmap", "netexec", "nxc"}
DOMAIN_TOOLS: Set[str] = {"subfinder", "whois", "dnspython"}
WORDLIST_TOOLS: Set[str] = {"gobuster", "ffuf"}

DEFAULT_TOOL_TARGETS: dict[str, str] = {
    "nmap": "127.0.0.1",
    "netexec": "127.0.0.1",
    "gobuster": "http://scanme.nmap.org",
    "nikto": "http://scanme.nmap.org",
    "ffuf": "http://scanme.nmap.org",
    "nuclei": "http://scanme.nmap.org",
    "sqlmap": "http://testphp.vulnweb.com/listproducts.php?cat=1",
    "subfinder": "example.com",
    "whois": "example.com",
    "dnspython": "example.com",
    "searchsploit": "Apache 2.4.49",
}

TOOL_TARGET_GUIDANCE: dict[str, dict[str, Any]] = {
    "nmap": {
        "expected_format": "IPv4 (127.0.0.1), IPv6 (::1), CIDR (192.168.1.0/24), IP Range (10.0.0.1-50), or Hostname (scanme.nmap.org)",
        "safe_sandbox": "127.0.0.1 (local loopback) or scanme.nmap.org (Nmap authorized test server)",
        "permissible": [
            "Local loopback (127.0.0.1, localhost) for inspecting locally listening daemons and ports.",
            "Official Nmap project sandbox (scanme.nmap.org) for testing version and script scans.",
            "Private lab subnets (10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16) and container bridge networks with explicit authorization.",
        ],
        "prohibited": [
            "Cloud metadata endpoints (169.254.169.254, 169.254.169.250, fd00:ec2::254) — potential SSRF vulnerability.",
            "Third-party production infrastructure, government, banking, healthcare, or military IP ranges without written Rules of Engagement (RoE).",
            "Broadcast or multicast addresses (e.g. 255.255.255.255, 224.0.0.1) which can cause network amplification storms.",
        ],
        "precautions": [
            "Aggressive timing templates (-T4, -T5) and full port sweeps (-p-) can saturate network firewalls, exhaust state tables, or crash fragile legacy embedded hardware.",
            "SYN half-open scans (-sS) require raw socket capabilities (root/sudo privileges).",
            "UDP scanning (-sU) is subject to OS-level ICMP rate limits (RFC 1812); expect scans to run significantly slower.",
        ],
        "general_knowledge": "Nmap interrogates the target's TCP/IP stack implementation using raw socket probes. It distinguishes open, closed, and filtered states via SYN-ACK, RST, or ICMP unreachable responses. Service versioning (-sV) probes matching service banners against nmap-service-probes.",
    },
    "netexec": {
        "expected_format": "Target IPv4 (127.0.0.1), CIDR subnet (192.168.1.0/24), or NetBIOS/FQDN hostname (dc01.corp.local)",
        "safe_sandbox": "127.0.0.1 (local Samba/SSH services) or dedicated Active Directory lab ranges (e.g., GOAD, HackTheBox)",
        "permissible": [
            "Local machine (127.0.0.1) for testing null sessions or guest share enumerations against local SMB daemons.",
            "Isolated Active Directory lab environments configured specifically for pentesting education.",
            "Authorized enterprise client subnets during approved engagement windows.",
        ],
        "prohibited": [
            "Production Active Directory Domain Controllers during business hours without explicit change approval.",
            "Internet-facing public SMB (port 445) endpoints not owned by you.",
            "Cloud link-local metadata addresses (169.254.169.254).",
        ],
        "precautions": [
            "Credential spraying (-u users.txt -p pass.txt) can trip Active Directory Account Lockout policies, locking out entire enterprise departments in minutes. Always inspect password policy first (--pass-pol).",
            "Pass-the-Hash and command execution (--exec) leave extensive event log trails (Event ID 4624, 4672, 7045) on Windows systems.",
            "Generating relay lists (--gen-relay-list) identifies SMB signing disabled hosts; do not execute relay attacks without explicit authorization.",
        ],
        "general_knowledge": "NetExec (successor to CrackMapExec) is a post-exploitation and protocol auditing framework. It automates testing credentials and configurations across SMB, WinRM, WMI, LDAP, MSSQL, SSH, and RDP.",
    },
    "gobuster": {
        "expected_format": "Complete HTTP or HTTPS URL (http://scanme.nmap.org, http://127.0.0.1:8080, https://example.com)",
        "safe_sandbox": "http://scanme.nmap.org or local container applications (http://127.0.0.1:8000)",
        "permissible": [
            "Local development servers, containerized CTF challenges (Juice Shop, DVWA, WebGoat).",
            "scanme.nmap.org for testing path discovery rate and status code filtering.",
            "Scoped web applications with written authorization from the domain owner.",
        ],
        "prohibited": [
            "Production e-commerce, banking, or healthcare web applications without explicit approval.",
            "Unmetered third-party APIs that incur financial cost or rate bans for the target owner.",
            "Cloud metadata URIs (http://169.254.169.254/latest/meta-data/).",
        ],
        "precautions": [
            "High concurrency (-t 50+) can overwhelm low-spec web servers, exhausting Apache/Nginx worker pools and causing HTTP 503 Service Unavailable.",
            "Brute-forcing on applications with automatic WAF or anti-bot systems (Cloudflare, AWS WAF) will trigger IP bans.",
            "Be mindful of wordlist size: large wordlists (100k+ paths) generate massive access log files that consume server disk space.",
        ],
        "general_knowledge": "Gobuster performs deterministic dictionary traversal by appending wordlist entries to the base URL and inspecting HTTP response status codes (200 OK, 301/302 Redirect, 403 Forbidden). It runs concurrent goroutines for maximum throughput.",
    },
    "nikto": {
        "expected_format": "Hostname (scanme.nmap.org), IP (127.0.0.1), or HTTP/HTTPS URL (http://scanme.nmap.org)",
        "safe_sandbox": "http://scanme.nmap.org or local Apache/Nginx web server instances",
        "permissible": [
            "Local web servers (http://127.0.0.1:8080) to inspect default files, outdated modules, and missing security headers.",
            "Authorized client web applications during penetration tests.",
            "Designated academic or lab targets.",
        ],
        "prohibited": [
            "Third-party production websites without written authorization.",
            "Any target where stealth is required: Nikto is completely unstealthy and intentionally issues thousands of noisy exploit requests.",
            "Cloud metadata endpoints (169.254.169.254).",
        ],
        "precautions": [
            "Nikto issues over 6,700 known vulnerability checks, dangerous CGI paths, and obsolete file requests. It WILL trigger IDS/IPS and SOC alerts.",
            "Avoid running full scans (-Tuning 2,4,b) against fragile legacy web servers or embedded IoT web interfaces, as old CGIs may cause crashes.",
            "Use -ssl when targeting HTTPS endpoints, and -p to specify custom ports.",
        ],
        "general_knowledge": "Nikto is a comprehensive web server misconfiguration scanner. It checks for over 6,700 potentially dangerous files/CGIs, outdated server software, insecure HTTP methods (TRACE, PUT), and missing defense headers (X-Frame-Options, CSP, HSTS).",
    },
    "ffuf": {
        "expected_format": "Complete HTTP/HTTPS URL containing the 'FUZZ' keyword (http://scanme.nmap.org/FUZZ, http://target/?FUZZ=1)",
        "safe_sandbox": "http://scanme.nmap.org/FUZZ or local lab applications (http://127.0.0.1:8000/FUZZ)",
        "permissible": [
            "Local and lab web services for directory fuzzing, virtual host discovery, and parameter enumeration.",
            "Authorized bug bounty targets that permit automated fuzzing within scope.",
            "scanme.nmap.org/FUZZ for syntax and rate testing.",
        ],
        "prohibited": [
            "Form endpoints that trigger emails, database writes, or financial transactions (e.g. /contact.php?email=FUZZ, /checkout?item=FUZZ).",
            "Cloud metadata endpoints (http://169.254.169.254).",
            "Out-of-scope third-party websites.",
        ],
        "precautions": [
            "ffuf is written in Go and can exceed 2,000+ requests per second. Always enforce rate limits (-rate 30 -p 0.1) on shared infrastructure.",
            "Match and filter flags (-mc, -fc, -fs, -fl) are essential: without proper filtering, wildcard responses will flood your results.",
            "Virtual host fuzzing requires proper Host header syntax (-H 'Host: FUZZ.domain.com') with a clean domain name.",
        ],
        "general_knowledge": "ffuf (Fuzz Faster U Fool) replaces the FUZZ keyword in URLs, headers, or request bodies with entries from a wordlist. It analyzes response length, word count, line count, and status code distributions to identify anomalous responses.",
    },
    "nuclei": {
        "expected_format": "Complete HTTP or HTTPS URL (http://scanme.nmap.org, https://example.com) or network host",
        "safe_sandbox": "http://scanme.nmap.org or intentionally vulnerable test applications (Vulnweb, DVWA)",
        "permissible": [
            "Local lab applications, Dockerized targets, and authorized bug bounty scopes.",
            "scanme.nmap.org for benign technology and SSL/TLS fingerprinting.",
            "Production assets when restricted to informational or passive templates (-severity info -tags tech).",
        ],
        "prohibited": [
            "Running intrusive exploit templates (-tags rce,sqli,takeover) against production systems without explicit authorization.",
            "Cloud metadata endpoints (169.254.169.254).",
            "Unowned third-party targets.",
        ],
        "precautions": [
            "Template concurrency (-c) and rate limiting (-rate-limit) should be configured to prevent saturating target network bandwidth.",
            "Be aware of template categories: tags like 'exposure', 'misconfig', and 'tech' are generally safe, while 'cve' or 'exploit' may execute payload injections.",
            "Review template YAML logic before executing against sensitive enterprise targets.",
        ],
        "general_knowledge": "Nuclei uses declarative YAML templates to send targeted network requests and match responses via regex, status codes, and binary words. It avoids brute force by checking only known signature patterns.",
    },
    "sqlmap": {
        "expected_format": "Complete HTTP/HTTPS URL with parameters to test (http://testphp.vulnweb.com/listproducts.php?cat=1)",
        "safe_sandbox": "http://testphp.vulnweb.com/listproducts.php?cat=1 (Acunetix public SQLi testbed) or local lab DBs",
        "permissible": [
            "Public intentionally vulnerable lab environments (testphp.vulnweb.com).",
            "Local containerized SQLi labs (e.g. sqli-labs, DVWA, bWAPP).",
            "Explicitly scoped applications during penetration testing with database administrator awareness.",
        ],
        "prohibited": [
            "NEVER run against production databases or live customer transactional databases without written consent!",
            "E-commerce payment gateways, authentication portals, or medical databases.",
            "Cloud metadata endpoints.",
        ],
        "precautions": [
            "SQL injection probes can alter database state. Blind time-based SQLi (SLEEP, WAITFOR DELAY) can lock database worker threads and starve legitimate connections.",
            "Never use intrusive flags like --os-shell, --sql-shell, or --priv-esc without explicit permission and database backups in place.",
            "Start with conservative settings (--level=1 --risk=1 --batch) to avoid destructive payload generation.",
        ],
        "general_knowledge": "sqlmap automates the detection and exploitation of SQL injection flaws. It tests 6 injection techniques: Boolean-based blind, Error-based, Union query-based, Stacked queries, Time-based blind, and Inline queries.",
    },
    "subfinder": {
        "expected_format": "Clean root domain name (example.com, insecure.org). Do NOT include http:// or www.",
        "safe_sandbox": "example.com (IANA designated safe domain) or insecure.org (Nmap project domain)",
        "permissible": [
            "example.com for verifying tool execution and OSINT pipelines.",
            "Your organization's registered domains for external attack surface mapping.",
            "Client target domains during authorized reconnaissance engagements.",
        ],
        "prohibited": [
            "Target domains outside your engagement's defined scope.",
            "Attempting to query internal non-routable domains (.local, .internal) via public OSINT sources.",
        ],
        "precautions": [
            "Subfinder is completely passive: it queries public data sources (Search engines, Certificate Transparency logs, VirusTotal, Censys) and never sends packets to the target domain directly.",
            "Respect public API rate limits: configure provider API keys in subfinder configuration to avoid IP throttling.",
            "Subdomains discovered may point to decommissioned servers (potential Subdomain Takeover vulnerability).",
        ],
        "general_knowledge": "Subfinder discovers valid subdomains for websites by using passive online sources. It operates silently without generating IDS/IPS alerts on the target's infrastructure, making it ideal for the initial OSINT phase.",
    },
    "whois": {
        "expected_format": "Domain name (example.com), Autonomous System Number (AS15169), or IP address (93.184.216.34)",
        "safe_sandbox": "example.com (IANA test domain) or public IP addresses (e.g. 8.8.8.8)",
        "permissible": [
            "example.com for verifying registrar and ownership data structures.",
            "Any public domain, IP address, or ASN within standard registry lookup terms.",
            "Client domains and allocated netblocks during initial reconnaissance.",
        ],
        "prohibited": [
            "High-frequency automated scraping loops that violate Regional Internet Registry (RIR) acceptable use policies.",
            "Internal private IP addresses (10.0.0.0/8, 192.168.0.0/16, 172.16.0.0/12) which yield no public registry data.",
        ],
        "precautions": [
            "WHOIS servers (TCP port 43) strictly enforce IP rate limits. Exceeding query thresholds will result in temporary or permanent IP bans.",
            "Modern GDPR and ICANN privacy redaction policies frequently mask personal registrant names and emails behind privacy proxies.",
            "Use -h to query specific regional registries directly (e.g., whois.arin.net, whois.ripe.net).",
        ],
        "general_knowledge": "The WHOIS protocol (RFC 3912) queries distributed databases maintained by TLD registries, registrars, and Regional Internet Registries (ARIN, RIPE NCC, APNIC, LACNIC, AFRINIC) to determine domain registration, nameservers, and IP allocations.",
    },
    "dnspython": {
        "expected_format": "Domain name (example.com) or IPv4 address for reverse pointer lookups (e.g. 93.184.216.34)",
        "safe_sandbox": "example.com (RFC 2606 safe domain) or local DNS test environments (BIND9, CoreDNS)",
        "permissible": [
            "example.com for querying A, AAAA, MX, NS, TXT, and SOA records.",
            "Your authorized target domains for DNS configuration auditing and mail routing inspection.",
            "Local or lab DNS servers for testing Zone Transfers (AXFR).",
        ],
        "prohibited": [
            "Unauthorized Zone Transfer (AXFR) attempts against production third-party nameservers.",
            "DNS amplification or flooding attacks against public recursive resolvers (8.8.8.8, 1.1.1.1).",
            "Cloud metadata endpoints.",
        ],
        "precautions": [
            "Zone Transfers (AXFR) will be logged on authoritative nameservers. An open zone transfer is a high-severity finding that leaks entire internal network namespaces.",
            "When auditing email anti-spoofing (SPF, DMARC), verify that TXT records are syntactically valid and enforce reject policies (p=reject).",
            "Be aware of DNS caching: queries might return cached intermediate results from your upstream resolver rather than authoritative values.",
        ],
        "general_knowledge": "dnspython is a pure-Python DNS toolkit. It constructs standard RFC 1035 UDP/TCP wire packets to interrogate nameservers directly. It verifies record types (A, MX, NS, TXT, PTR) and evaluates defensive controls like DNSSEC and zone transfer ACLs.",
    },
    "searchsploit": {
        "expected_format": "Software name and version string (Apache 2.4.49, OpenSSH 7.2p2) or CVE ID (2021-41773). Do NOT use URLs or IPs.",
        "safe_sandbox": "Apache 2.4.49 (famous CVE-2021-41773 RCE), ProFTPD 1.3.5, vsftpd 2.3.4",
        "permissible": [
            "Searching for known public exploits, PoC scripts, and papers from the local Exploit-DB archive.",
            "Filtering by title, CVE identifier, platform (Linux/Windows), or remote exploit type.",
            "Offline query analysis with zero network footprint.",
        ],
        "prohibited": [
            "NEVER compile or execute downloaded public exploit code against live systems without auditing the source code in an isolated VM sandbox first!",
            "Do not enter raw IP addresses or URLs as search terms; searchsploit searches text descriptions and version metadata.",
        ],
        "precautions": [
            "SearchSploit operates 100% locally and offline: it queries the local exploitdb repository (/usr/share/exploitdb/) without contacting external networks.",
            "Public exploits on Exploit-DB often require modification (offsets, shellcode, return addresses) to function on specific target builds.",
            "Some public PoCs in the wild may contain trojanized payloads or malicious backdoors. Always inspect C/Python/Perl source code thoroughly before execution.",
        ],
        "general_knowledge": "SearchSploit is a command-line search utility for Exploit-DB. It enables rapid offline correlation between banner versions discovered during reconnaissance and publicly weaponized vulnerability proofs-of-concept.",
    },
}


def get_tool_target_guidance(tool_name: str) -> str:
    """Format structured target selection rules, sandbox recommendations, and operational precautions as Markdown."""
    guidance = TOOL_TARGET_GUIDANCE.get(tool_name.lower())
    if not guidance:
        return ""

    lines = [
        "## 🎯 Target Scope, Permissible Usage & Operational Precautions\n",
        f"**Expected Target Syntax**: `{guidance['expected_format']}`  ",
        f"**Recommended Safe Sandbox**: `{guidance['safe_sandbox']}`\n",
        "### ✅ Permissible & Effective Targets",
    ]
    for item in guidance["permissible"]:
        lines.append(f"- {item}")

    lines.append("\n### ⛔ Strictly Prohibited & Dangerous Targets")
    for item in guidance["prohibited"]:
        lines.append(f"- {item}")

    lines.append("\n### ⚠️ Operational Precautions & Ethics")
    for item in guidance["precautions"]:
        lines.append(f"- {item}")

    lines.append("\n### 💡 General Tool Knowledge & Kill-Chain Context")
    lines.append(f"> {guidance['general_knowledge']}\n")

    return "\n".join(lines)


WORDLIST_FLAG_REGEX = re.compile(
    r"(?:^|\s)(?:-w|--wordlist)(?:=|\s+)(\S+)",
    re.IGNORECASE,
)


@dataclass
class PreflightIssue:
    """An individual issue or recommendation identified during preflight checks."""

    category: Literal["binary", "wordlist", "target", "security"]
    severity: Literal["error", "warning"]
    title: str
    description: str
    remediation_hint: str
    can_auto_remedy: bool = False
    remedy_label: Optional[str] = None
    remedy_action: Optional[str] = None
    remedy_payload: Optional[str] = None


@dataclass
class PreflightReport:
    """Consolidated outcome of preflight verification for a proposed command."""

    tool_name: str
    target: str
    flags: str
    issues: List[PreflightIssue] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        """True if there are zero blocking errors."""
        return not any(i.severity == "error" for i in self.issues)

    @property
    def has_warnings(self) -> bool:
        """True if there are non-blocking warnings."""
        return any(i.severity == "warning" for i in self.issues)

    @property
    def errors(self) -> List[PreflightIssue]:
        return [i for i in self.issues if i.severity == "error"]

    @property
    def warnings(self) -> List[PreflightIssue]:
        return [i for i in self.issues if i.severity == "warning"]

    @property
    def remediable_issues(self) -> List[PreflightIssue]:
        return [i for i in self.issues if i.can_auto_remedy]


class PreflightVerifier:
    """Deep module verifying tool dependencies, wordlist assets, target parameters,

    and security boundaries prior to subprocess dispatch.
    """

    def __init__(
        self,
        registry: Optional[Any] = None,
        wordlists_dir: Optional[str] = None,
    ):
        self.registry = registry
        self.wordlists_dir = wordlists_dir

    def verify(
        self,
        tool_name: str,
        target: str,
        flags: str = "",
        recipe_idx: Optional[int] = None,
    ) -> PreflightReport:
        """Run comprehensive preflight verification and return a structured report."""
        clean_tool = (tool_name or "").strip().lower()
        clean_target = (target or "").strip()
        clean_flags = (flags or "").strip()

        report = PreflightReport(
            tool_name=clean_tool,
            target=clean_target,
            flags=clean_flags,
            issues=[],
        )

        if not clean_tool:
            report.issues.append(
                PreflightIssue(
                    category="binary",
                    severity="error",
                    title="No security tool selected",
                    description="An active security tool must be selected before executing scans.",
                    remediation_hint="Select a tool from the catalog or recipe deck.",
                )
            )
            return report

        # 1. Binary Availability Check
        self._check_binary(clean_tool, report)

        # 2. Security Gating (Sudo & SSRF)
        self._check_security(clean_tool, clean_target, clean_flags, report)

        # 3. Target Variable & Scheme Validation
        self._check_target(clean_tool, clean_target, report)

        # 4. Wordlist Assets Validation
        self._check_wordlists(clean_tool, clean_flags, report)

        return report

    @staticmethod
    def quick_check(
        tool_name: str,
        target: str,
        flags: str = "",
    ) -> Optional[str]:
        """Perform a fast, non-blocking check returning a single concise warning string if any issue exists."""
        clean_target = (target or "").strip()
        clean_flags = (flags or "").strip()
        clean_tool = (tool_name or "").strip().lower()

        if re.search(r"\bsudo\b", clean_flags) or re.search(r"\bsudo\b", clean_target):
            return "[!] Sudo execution is prohibited in Learning Mode."

        if not clean_target:
            return "[!] Target address or host is required."

        if is_blocked_destination(clean_target):
            return "[!] Target is blocked by cloud metadata policy."

        if any(var in clean_target for var in ("$TARGET", "{target}", "{url}", "$PORT")):
            return "[!] Target contains unexpanded variable placeholder."

        if clean_tool in WEB_TOOLS:
            if not clean_target.startswith("http://") and not clean_target.startswith("https://"):
                return f"[!] Web tool '{clean_tool}' expects 'http://' or 'https://' prefix."

        if clean_tool in NETWORK_TOOLS:
            if clean_target.startswith("http://") or clean_target.startswith("https://"):
                return f"[!] Network tool '{clean_tool}' expects bare IP or hostname, not URL."

        return None

    def apply_remedy(
        self,
        issue: PreflightIssue,
        target: str,
        flags: str = "",
    ) -> Tuple[str, str, Optional[str]]:
        """Apply an automated one-click remediation to an identified preflight issue.

        Returns:
            Tuple of (updated_target, updated_flags, feedback_message)
        """
        action = issue.remedy_action
        payload = issue.remedy_payload

        if action == "seed_wordlists":
            dest_dir = self.wordlists_dir or paths.get_default_wordlists_dir()
            extracted = seed_bundled_wordlists(dest_dir)
            msg = f"Extracted {len(extracted)} starter wordlists to ~/.cyguide/wordlists/."
            return target, flags, msg

        elif action == "fix_target_scheme":
            new_target = payload if payload else f"http://{target.strip()}"
            return new_target, flags, f"Updated target to: {new_target}"

        elif action == "strip_url_scheme":
            new_target = payload if payload else self._extract_clean_hostname(target)
            return new_target, flags, f"Stripped URL scheme: {new_target}"

        elif action == "set_default_target":
            new_target = payload or "127.0.0.1"
            return new_target, flags, f"Set target to test address: {new_target}"

        elif action == "remove_sudo":
            new_flags = re.sub(r"\bsudo\s*", "", flags).strip()
            return target, new_flags, "Removed 'sudo' from command parameters."

        elif action == "copy_install_command":
            return target, flags, payload or issue.remediation_hint

        return target, flags, None

    # --- Internal Verification Rules ---

    def _check_binary(self, tool_name: str, report: PreflightReport) -> None:
        """Verify that the tool's binary is installed and discoverable."""
        if tool_name == "dnspython":
            # Pure-Python probe; always installed
            return

        adapter = None
        manifest = None
        if self.registry:
            tool_data = self.registry.get_tool(tool_name)
            if tool_data:
                adapter = tool_data.get("adapter")
                manifest = tool_data.get("manifest")

        is_installed = False
        binary_name = tool_name
        if manifest and hasattr(manifest, "meta") and getattr(manifest.meta, "binary", None):
            binary_name = manifest.meta.binary
        elif adapter and hasattr(adapter, "binary"):
            binary_name = adapter.binary

        if adapter and hasattr(adapter, "validate_install"):
            try:
                is_installed = bool(adapter.validate_install())
            except Exception:
                is_installed = False
        else:
            is_installed = bool(shutil.which(binary_name))

        if not is_installed:
            hint = (
                INSTALLATION_HINTS.get(tool_name)
                or INSTALLATION_HINTS.get(binary_name)
                or f"sudo apt install {binary_name}"
            )
            report.issues.append(
                PreflightIssue(
                    category="binary",
                    severity="error",
                    title=f"Tool binary '{binary_name}' is not installed",
                    description=f"The executable '{binary_name}' was not found in system PATH.",
                    remediation_hint=hint,
                    can_auto_remedy=True,
                    remedy_label="Copy Install Command",
                    remedy_action="copy_install_command",
                    remedy_payload=hint,
                )
            )

    def _check_security(
        self,
        tool_name: str,
        target: str,
        flags: str,
        report: PreflightReport,
    ) -> None:
        """Enforce sandbox security restrictions (sudo ban, SSRF link-local gating)."""
        # Sudo ban in Learning Mode
        if re.search(r"\bsudo\b", flags) or re.search(r"\bsudo\b", target):
            report.issues.append(
                PreflightIssue(
                    category="security",
                    severity="error",
                    title="Privilege escalation ('sudo') is prohibited",
                    description="Commands cannot be executed with elevated root privileges in Learning Mode.",
                    remediation_hint="Remove 'sudo' from command parameters.",
                    can_auto_remedy=True,
                    remedy_label="Remove sudo",
                    remedy_action="remove_sudo",
                    remedy_payload=re.sub(r"\bsudo\s*", "", flags).strip(),
                )
            )

        # SSRF Link-Local Metadata Protection
        if target and is_blocked_destination(target):
            report.issues.append(
                PreflightIssue(
                    category="security",
                    severity="error",
                    title=f"Target '{target}' is blocked by security policy",
                    description="Target destination matches prohibited cloud provider metadata or link-local subnet.",
                    remediation_hint="Choose a valid authorized target or local loopback address (127.0.0.1).",
                    can_auto_remedy=True,
                    remedy_label="Set 127.0.0.1",
                    remedy_action="set_default_target",
                    remedy_payload="127.0.0.1",
                )
            )

    def _check_target(
        self,
        tool_name: str,
        target: str,
        report: PreflightReport,
    ) -> None:
        """Validate target presence, unresolved variable placeholders, and tool scheme alignment."""
        is_web = tool_name in WEB_TOOLS
        default_target = DEFAULT_TOOL_TARGETS.get(
            tool_name, "http://127.0.0.1:8888" if is_web else "127.0.0.1"
        )

        if not target:
            report.issues.append(
                PreflightIssue(
                    category="target",
                    severity="error",
                    title="Target address or host is missing",
                    description="Security tools require an active target IP, domain, or URL to execute.",
                    remediation_hint=f"Provide a target or use local sandbox target '{default_target}'.",
                    can_auto_remedy=True,
                    remedy_label=f"Set '{default_target}'",
                    remedy_action="set_default_target",
                    remedy_payload=default_target,
                )
            )
            return

        # Check for unexpanded placeholder variables
        unexpanded = [
            var for var in ("$TARGET", "{target}", "{url}", "$PORT", "{domain}") if var in target
        ]
        if unexpanded:
            report.issues.append(
                PreflightIssue(
                    category="target",
                    severity="error",
                    title=f"Unexpanded variable placeholder: '{unexpanded[0]}'",
                    description=f"The target contains an unresolved token '{unexpanded[0]}' instead of an actual address.",
                    remediation_hint="Replace variable with an actual IP address, domain, or URL.",
                    can_auto_remedy=True,
                    remedy_label=f"Set '{default_target}'",
                    remedy_action="set_default_target",
                    remedy_payload=default_target,
                )
            )
            return

        # Web Tool URL Scheme Validation
        if is_web:
            if not target.startswith("http://") and not target.startswith("https://"):
                report.issues.append(
                    PreflightIssue(
                        category="target",
                        severity="error",
                        title=f"Web tool '{tool_name}' requires an HTTP/HTTPS URL",
                        description=f"Target '{target}' is missing the 'http://' or 'https://' protocol scheme required by web fuzzers.",
                        remediation_hint=f"Prepend 'http://' to the target: 'http://{target}'.",
                        can_auto_remedy=True,
                        remedy_label="Add http:// Prefix",
                        remedy_action="fix_target_scheme",
                        remedy_payload=f"http://{target}",
                    )
                )

        # Network Tool Bare Host Validation
        elif tool_name in NETWORK_TOOLS:
            if target.startswith("http://") or target.startswith("https://"):
                clean_host = self._extract_clean_hostname(target)
                report.issues.append(
                    PreflightIssue(
                        category="target",
                        severity="warning",
                        title=f"Network tool '{tool_name}' expects a host or IP, not a URL",
                        description=f"Target '{target}' contains URL protocol schemes that can cause scanner errors.",
                        remediation_hint=f"Use bare hostname or IP '{clean_host}' instead of URL.",
                        can_auto_remedy=True,
                        remedy_label=f"Use '{clean_host}'",
                        remedy_action="strip_url_scheme",
                        remedy_payload=clean_host,
                    )
                )

    def _check_wordlists(
        self,
        tool_name: str,
        flags: str,
        report: PreflightReport,
    ) -> None:
        """Inspect command flags for wordlist dependencies and ensure required files exist."""
        dest_dir = self.wordlists_dir or paths.get_default_wordlists_dir()
        dest_path = Path(dest_dir)
        available = (
            {f.stem: str(f.resolve()) for f in dest_path.glob("*.txt")}
            if dest_path.is_dir()
            else {}
        )

        # 1. Macro Tokens: {wordlist:name} or {wordlist}
        macro_matches = WORDLIST_MACRO_REGEX.findall(flags)
        for named in macro_matches:
            wl_key = named.strip() if named else DEFAULT_WORDLIST_NAME
            if wl_key.endswith(".txt"):
                wl_key = wl_key[:-4]

            if wl_key not in available:
                report.issues.append(
                    PreflightIssue(
                        category="wordlist",
                        severity="error",
                        title=f"Wordlist '{wl_key}' is not available on disk",
                        description=f"The required wordlist asset '{wl_key}.txt' is missing from {dest_dir}.",
                        remediation_hint="Install bundled starter wordlists into ~/.cyguide/wordlists/.",
                        can_auto_remedy=True,
                        remedy_label="Seed Bundled Wordlists",
                        remedy_action="seed_wordlists",
                        remedy_payload=wl_key,
                    )
                )

        # 2. CLI flags: -w <path> or --wordlist <path>
        # Only evaluate wordlist file paths for tools that consume wordlists or explicit --wordlist
        is_wordlist_tool = tool_name in WORDLIST_TOOLS or "--wordlist" in flags
        if is_wordlist_tool:
            flag_matches = WORDLIST_FLAG_REGEX.findall(flags)
            for raw_path in flag_matches:
                clean_path = raw_path.strip().strip("'\"")
                # If path starts with '-' or contains macros, it's not a wordlist file path
                if clean_path.startswith("-") or ("{" in clean_path and "}" in clean_path):
                    continue

                expanded = os.path.abspath(os.path.expanduser(clean_path))
                if not os.path.isfile(expanded):
                    report.issues.append(
                        PreflightIssue(
                            category="wordlist",
                            severity="error",
                            title=f"Specified wordlist file not found: '{clean_path}'",
                            description=f"Path '{expanded}' does not exist on disk.",
                            remediation_hint="Verify the wordlist path or seed bundled starter dictionaries.",
                            can_auto_remedy=True,
                            remedy_label="Seed Bundled Wordlists",
                            remedy_action="seed_wordlists",
                            remedy_payload="common_dirs",
                        )
                    )

    @staticmethod
    def _extract_clean_hostname(url_or_target: str) -> str:
        """Extract a clean host/IP from an address that might contain schemes, ports, or paths."""
        try:
            parsed = urllib.parse.urlparse(url_or_target)
            if parsed.hostname:
                return parsed.hostname
        except Exception:
            pass
        cleaned = re.sub(r"^https?://", "", url_or_target)
        return cleaned.split("/")[0].split(":")[0]
