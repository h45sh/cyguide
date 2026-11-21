"""NetExec (nxc) tool adapter."""

import re
import shlex
import shutil
from typing import Any, AsyncIterator, Dict, List, Optional

from cyguide.engine.adapter import ToolAdapter
from cyguide.engine.wordlists import substitute_wordlist_macros
from cyguide.schemas.base import BaseFinding
from cyguide.schemas.credential import CredentialFound
from cyguide.schemas.network import NetworkHost, NetworkService
from cyguide.schemas.vulnerability import AuditMisconfig


class NetexecAdapter(ToolAdapter):
    """Adapter for the NetExec network execution and credential spraying tool."""

    LINE_RE = re.compile(
        r"^(?P<proto>[A-Z0-9]+)\s+(?P<ip>[0-9a-fA-F\.:]+)\s+(?P<port>\d+)\s+(?P<hostname>\S+)\s+(?P<status>\[[\+\-\*]\])\s+(?P<message>.*)$"
    )
    CRED_RE = re.compile(
        r"(?:(?P<domain>[^\s\\:]+)\\)?(?P<user>[^:\s]+):(?P<pass>\S+)(?:\s+\((?P<pwn3d>[^)]+)\))?"
    )

    def validate_install(self) -> bool:
        """Check if nxc or netexec binary is present in system PATH."""
        return self.is_binary_available("nxc") or self.is_binary_available("netexec")

    def sanitize_output(self, raw_stdout: str) -> str:
        """Strip NetExec startup headers and noise lines."""
        lines = []
        for line in raw_stdout.splitlines():
            s = line.strip()
            if (
                s.startswith("NetExec v")
                or "[*] NetExec Active Directory" in s
                or s.startswith("---")
            ):
                continue
            lines.append(line)
        return "\n".join(lines)

    def build_command(self, target: BaseFinding, params: Dict[str, Any]) -> List[str]:
        """Construct NetExec command line execution arguments."""
        bin_name = "nxc" if shutil.which("nxc") else "netexec"

        target_addr = self.extract_host(target)

        raw_flags = params.get("raw_flags", "").strip()
        raw_flags, _ = substitute_wordlist_macros(raw_flags)
        flag_args = shlex.split(raw_flags) if raw_flags else []

        args = [bin_name]

        # 1. Check if protocol is already in flag_args (e.g. smb, ssh, ldap, winrm)
        known_protocols = {"smb", "ssh", "ldap", "winrm", "wmi", "mssql", "rdp", "vnc", "ftp"}
        has_protocol = bool(flag_args and flag_args[0].lower() in known_protocols)

        if not has_protocol:
            args.append("smb")

        # 2. Check if target address is provided in flag_args
        if not any(arg == target_addr for arg in flag_args):
            if not target_addr:
                raise ValueError(
                    f"Target finding {target.schema_type} has no IP or host address, and none provided in flags."
                )
            # Insert target right after protocol if protocol was in flag_args[0], else append
            args.append(target_addr)

        args.extend(flag_args)
        return args

    def _extract_target(self, target: BaseFinding) -> Optional[str]:
        return self.extract_host(target)

    async def parse_output(
        self, raw_stdout: str, target: BaseFinding, context: Dict[str, Any] = None
    ) -> AsyncIterator[BaseFinding]:
        """Parse NetExec stdout into NetworkHost, NetworkService, AuditMisconfig, and CredentialFound findings."""
        cleaned = raw_stdout.strip()
        if not cleaned:
            return

        seen_hosts = set()
        seen_services = set()
        seen_misconfigs = set()
        seen_creds = set()

        for line in cleaned.splitlines():
            line_str = line.strip()
            match = self.LINE_RE.match(line_str)
            if not match:
                continue

            proto = match.group("proto").lower()
            ip = match.group("ip")
            port = int(match.group("port"))
            hostname = match.group("hostname")
            status = match.group("status")
            message = match.group("message").strip()

            # 1. Register host and service
            if ip not in seen_hosts:
                seen_hosts.add(ip)
                yield NetworkHost.create(ip=ip, hostname=hostname if hostname != ip else None)

            service_key = (ip, port, proto)
            if service_key not in seen_services:
                seen_services.add(service_key)
                yield NetworkService.create(
                    host_ip=ip,
                    port=port,
                    protocol="tcp",
                    service_name=proto,
                )

            # 2. Check for SMB signing misconfiguration
            if "signing:False" in message:
                misconfig_key = (ip, port, "smb_signing_disabled")
                if misconfig_key not in seen_misconfigs:
                    seen_misconfigs.add(misconfig_key)
                    yield AuditMisconfig.create(
                        target=f"{proto}://{ip}:{port}",
                        check_id="smb_signing_disabled",
                        title="SMB Signing Disabled",
                        severity="medium",
                        description=(
                            f"Host {hostname} ({ip}) does not require SMB signing, "
                            f"exposing the system to NTLM relay attacks."
                        ),
                        remediation=(
                            "Enforce 'Digitally sign communications (always)' in Windows Group Policy."
                        ),
                        host_ip=ip,
                        port=port,
                    )

            # 3. Check for successful credentials [+]
            if status == "[+]":
                cred_match = self.CRED_RE.search(message)
                if cred_match:
                    domain = cred_match.group("domain") or "LOCAL"
                    user = cred_match.group("user")
                    password = cred_match.group("pass")
                    pwn3d = bool(cred_match.group("pwn3d"))

                    # Ignore non-credential success lines like "[+] Enumerated shares:"
                    if user.lower() in ("enumerated", "pwn3d!", "shares:"):
                        continue

                    cred_key = (domain, user, password, ip)
                    if cred_key not in seen_creds:
                        seen_creds.add(cred_key)
                        yield CredentialFound.create(
                            context=f"{proto}://{domain}",
                            username=user,
                            password=password,
                            host_ip=ip,
                            pwn3d=pwn3d,
                            domain=domain,
                        )
