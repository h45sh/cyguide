"""Validation and policy enforcement for tool actions."""

from typing import Optional
from cyguide.schemas.power import ActionRequest, ActionSource
from cyguide.engine.registry import ToolRegistry
from cyguide.engine.store import GraphStore


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
        # 1. Resolve Tool
        tool_data = self.registry.get_tool(action.tool_name)
        
        # 2. Policy: Handle Shell Commands
        if not tool_data:
            # Only allow arbitrary shell commands if explicitly requested (!) and by a user
            if action.is_explicit_shell and action.triggered_by == ActionSource.USER:
                return True
            
            # If not explicit or not user, reject
            reason = "is not a registered tool"
            if not action.is_explicit_shell:
                reason += " and no explicit shell prefix ('!') was provided"
            
            raise ActionValidationError(f"Action '{action.tool_name}' {reason}.")

        # 3. Standard Validation for Registered Tools
        manifest = tool_data["manifest"]

        # 4. Check if target entity exists and is compatible
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

        target_schema = node["schema_type"]
        accepted_inputs = manifest.input.get("accepts", [])
        if target_schema not in accepted_inputs:
            raise ActionValidationError(
                f"Tool '{action.tool_name}' does not accept input type '{target_schema}'. "
                f"Accepted types: {', '.join(accepted_inputs)}"
            )

        # 3. Policy: (Future) Check CIDR scopes, blocked flags, etc.
        # For now, we just pass.

        return True
