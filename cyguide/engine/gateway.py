"""Validation and policy enforcement for tool actions."""

from cyguide.schemas.power import ActionRequest, ActionSource
from cyguide.engine.registry import ToolRegistry
from cyguide.engine.store import GraphStore


BLOCKED_TARGETS = {
    "169.254.",                 # IPv4 Link-Local / Cloud Metadata (AWS, Azure, GCP, DigitalOcean, Oracle)
    "fd00:ec2::254",            # AWS IPv6 IMDSv2 metadata
    "100.100.100.200",          # Alibaba Cloud metadata
    "2852039166",               # Decimal notation of 169.254.169.254
    "0xa9fea9fe",               # Hex notation of 169.254.169.254
    "metadata.google.internal", # GCP metadata DNS
    "metadata.internal",        # Generic internal metadata DNS
    "instance-data",            # EC2 instance data hostname
}


def is_blocked_destination(text: str) -> bool:
    """Check if a string contains known restricted destinations like cloud metadata."""
    if not text:
        return False
    lower_text = text.lower()
    for blocked in BLOCKED_TARGETS:
        if blocked in lower_text:
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

    def __init__(self, registry: ToolRegistry, store: GraphStore):
        self.registry = registry
        self.store = store

    async def validate_action(self, action: ActionRequest) -> bool:
        """Validate an action request against registry and store state.

        Raises:
            ActionValidationError: If validation fails.
        """
        # 1. Enforce destination safety (block cloud metadata endpoints)
        raw_flags = action.params.get("raw_flags", "")
        if is_blocked_destination(raw_flags) or is_blocked_destination(action.tool_name):
            raise ActionValidationError("Access to cloud metadata endpoints is strictly prohibited.")

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
            raise ActionValidationError("Target entity points to a prohibited cloud metadata endpoint.")

        target_schema = node["schema_type"]
        accepted_inputs = manifest.input.get("accepts", [])
        if target_schema not in accepted_inputs:
            raise ActionValidationError(
                f"Tool '{action.tool_name}' does not accept input type '{target_schema}'. "
                f"Accepted types: {', '.join(accepted_inputs)}"
            )

        return True
