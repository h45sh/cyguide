"""Validation and policy enforcement for tool actions."""

import ipaddress
import socket
from typing import Any, Callable, Dict, List, Optional, Tuple

from cyguide import paths
from cyguide.common.algorithms import IPRadixTrie
from cyguide.engine.network import get_lhost_info
from cyguide.engine.registry import ToolRegistry
from cyguide.engine.store import GraphStore
from cyguide.schemas.power import ActionRequest, ActionSource


def _resolve_lhost() -> Tuple[Optional[str], Optional[str]]:
    import sys

    pf = sys.modules.get("cyguide.engine.power_facade")
    resolver = getattr(pf, "get_lhost_info", get_lhost_info) if pf else get_lhost_info
    try:
        return resolver()
    except Exception:
        return None, None


BLOCKED_TARGETS = {
    "169.254.",  # IPv4 Link-Local / Cloud Metadata (AWS, Azure, GCP, DigitalOcean, Oracle)
    "fd00:ec2::254",  # AWS IPv6 IMDSv2 metadata
    "100.100.100.200",  # Alibaba Cloud metadata
    "2852039166",  # Decimal notation of 169.254.169.254
    "0xa9fea9fe",  # Hex notation of 169.254.169.254
    "metadata.google.internal",  # GCP metadata DNS
    "metadata.internal",  # Generic internal metadata DNS
    "instance-data",  # EC2 instance data hostname
}

BLOCKED_NETWORKS = [
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("fe80::/10"),
    ipaddress.ip_network("fd00:ec2::/64"),
]

_BLOCKED_TRIE = IPRadixTrie()
for _net in BLOCKED_NETWORKS:
    _BLOCKED_TRIE.insert(_net)


def _parse_ip_candidate(candidate: str):
    """Attempt to parse an address token into an ipaddress object, resolving alternate numerical notations."""
    c = candidate.strip("\"'`()<>,;{}[]")
    if "://" in c:
        c = c.split("://", 1)[1]
    c = c.split("/", 1)[0]
    c = c.split("?", 1)[0]
    c = c.split("#", 1)[0]
    if c.startswith("[") and "]" in c:
        c = c[1 : c.index("]")]
    elif ":" in c and c.count(":") == 1:
        c = c.split(":", 1)[0]

    if not c:
        return None

    # Fast guard: valid IP candidates or alternate representations must have at least one digit or colon
    if not any(ch.isdigit() or ch == ":" for ch in c):
        return None

    try:
        return ipaddress.ip_address(c)
    except ValueError:
        pass

    try:
        raw_ip = socket.inet_ntoa(socket.inet_aton(c))
        return ipaddress.ip_address(raw_ip)
    except (OSError, ValueError):
        pass

    return None


def is_blocked_destination(text: str) -> bool:
    """Check if a string contains known restricted destinations like cloud metadata,
    canonicalizing alternative numerical notations (dotted-octal, dotted-hex, hex, and IPv4-mapped IPv6).
    """
    if not text:
        return False
    lower_text = text.lower()
    for blocked in BLOCKED_TARGETS:
        if blocked in lower_text:
            return True

    # Tokenize input to detect embedded IP candidates
    tokens = lower_text.replace("=", " ").replace("&", " ").replace(";", " ").split()
    for tok in tokens:
        ip_obj = _parse_ip_candidate(tok)
        if ip_obj is not None:
            # Check IPv4-mapped IPv6 (e.g. ::ffff:169.254.169.254)
            if hasattr(ip_obj, "ipv4_mapped") and ip_obj.ipv4_mapped:
                ip_obj = ip_obj.ipv4_mapped

            if _BLOCKED_TRIE.contains(ip_obj):
                return True

    return False


class ActionValidationError(Exception):
    """Raised when an ActionRequest fails validation."""

    pass


class ActionGateway:
    """The validation and policy layer for Power Mode.

    Ensures that any ActionRequest is legitimate, targets valid entities,
    and respects the tool's input contract before execution.
    """

    def __init__(
        self,
        registry: ToolRegistry,
        store: GraphStore,
        allowed_cidrs: Optional[List[str]] = None,
    ):
        self.registry = registry
        self.store = store
        self._allowed_cidrs: Optional[List[Any]] = None
        if allowed_cidrs:
            self.set_allowed_cidrs(allowed_cidrs)

    def set_allowed_cidrs(self, allowed_cidrs: Optional[List[str]]) -> None:
        """Configure declarative CIDR scope boundaries for engagements."""
        if not allowed_cidrs:
            self._allowed_cidrs = None
            self._allowed_cidrs_trie = None
        else:
            self._allowed_cidrs = [
                ipaddress.ip_network(c.strip(), strict=False) for c in allowed_cidrs if c.strip()
            ]
            self._allowed_cidrs_trie = IPRadixTrie()
            for net in self._allowed_cidrs:
                self._allowed_cidrs_trie.insert(net)

    def validate_target_scope(self, text_or_ip: str) -> bool:
        """Ensure any target IPs in text belong to the authorized engagement CIDR scope.

        Returns True if within scope (or if no scope restrictions are configured).
        """
        if not self._allowed_cidrs or not text_or_ip:
            return True

        tokens = text_or_ip.replace("=", " ").replace("&", " ").replace(";", " ").split()
        for tok in tokens:
            ip_obj = _parse_ip_candidate(tok)
            if ip_obj is not None:
                if hasattr(ip_obj, "ipv4_mapped") and ip_obj.ipv4_mapped:
                    ip_obj = ip_obj.ipv4_mapped
                trie = getattr(self, "_allowed_cidrs_trie", None)
                if trie is not None:
                    if not trie.contains(ip_obj):
                        return False
                else:
                    if not any(ip_obj in net for net in self._allowed_cidrs):
                        return False
        return True

    @staticmethod
    def resolve_entity_variables(
        pik: Optional[Dict[str, Any]] = None,
        lhost_resolver: Optional[Callable[[], Tuple[Optional[str], Optional[str]]]] = None,
    ) -> Dict[str, Any]:
        """Extract standard investigation variables ($TARGET, $PORT, $SERVICE, $PROTOCOL, $LHOST, $IFACE)."""
        resolved: Dict[str, Any] = {}
        if pik:
            target = pik.get("ip") or pik.get("domain") or pik.get("host_ip")
            if target:
                resolved["TARGET"] = target
            if "port" in pik:
                resolved["PORT"] = pik["port"]
            if "service" in pik:
                resolved["SERVICE"] = pik["service"]
            if "protocol" in pik:
                resolved["PROTOCOL"] = pik["protocol"]

        resolver = lhost_resolver or _resolve_lhost
        try:
            ip, iface = resolver()
            if ip:
                resolved["LHOST"] = ip
            if iface:
                resolved["IFACE"] = iface
        except Exception:
            pass

        resolved["WORDLIST"] = paths.get_wordlist_path("common_dirs")
        return resolved

    @staticmethod
    def interpolate_variables(text: str, variables: Dict[str, Any]) -> str:
        """Replace $VAR placeholders in command text with resolved values."""
        for var_name, val in variables.items():
            placeholder = f"${var_name}"
            if placeholder in text:
                text = text.replace(placeholder, str(val))
        return text

    async def validate_action(self, action: ActionRequest) -> bool:
        """Validate an action request against registry and store state.

        Raises:
            ActionValidationError: If validation fails.
        """
        # 1. Enforce destination safety (block cloud metadata endpoints)
        raw_flags = action.params.get("raw_flags", "")
        if is_blocked_destination(raw_flags) or is_blocked_destination(action.tool_name):
            raise ActionValidationError(
                "Access to cloud metadata endpoints is strictly prohibited."
            )

        # Enforce engagement CIDR scope boundaries if configured
        if self._allowed_cidrs and not self.validate_target_scope(raw_flags):
            raise ActionValidationError(
                "Target in command arguments violates authorized engagement CIDR scope."
            )

        # 2. Resolve Tool
        tool_data = self.registry.get_tool(action.tool_name)

        # 3. Policy: Handle Shell Commands
        if not tool_data:
            # Only allow arbitrary shell commands if explicitly requested (!) and by a user
            if action.is_explicit_shell and action.triggered_by == ActionSource.USER:
                return True

            # If not explicit or not user, reject
            reason = "is not a registered tool"
            if not action.is_explicit_shell:
                reason += " and no explicit shell prefix ('!') was provided"

            raise ActionValidationError(f"Action '{action.tool_name}' {reason}.")

        # 4. Standard Validation for Registered Tools
        manifest = tool_data["manifest"]

        # 5. Check if target entity exists and is compatible
        # POLICY: For manual USER actions, we allow execution without a selected entity
        # as they might be providing the target in the raw_flags (e.g., 'nmap 1.1.1.1')
        if not action.target_entity_id:
            if action.triggered_by == ActionSource.USER:
                return True
            raise ActionValidationError(
                f"Tool '{action.tool_name}' requires a selected target entity."
            )

        node = await self.store.get_node(str(action.session_id), action.target_entity_id)
        if not node:
            raise ActionValidationError(
                f"Target entity '{action.target_entity_id}' not found in session '{action.session_id}'."
            )

        # Enforce destination safety on the target entity
        pik_str = node.get("pik_json", "")
        if is_blocked_destination(pik_str):
            raise ActionValidationError(
                "Target entity points to a prohibited cloud metadata endpoint."
            )

        if self._allowed_cidrs and not self.validate_target_scope(pik_str):
            raise ActionValidationError(
                "Target entity IP violates authorized engagement CIDR scope."
            )

        target_schema = node["schema_type"]
        accepted_inputs = manifest.input.get("accepts", [])
        if target_schema not in accepted_inputs:
            raise ActionValidationError(
                f"Tool '{action.tool_name}' does not accept input type '{target_schema}'. "
                f"Accepted types: {', '.join(accepted_inputs)}"
            )

        return True
