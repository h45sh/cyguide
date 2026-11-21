"""Security tool ecosystem inspection and validation CLI command handler."""

from typing import Any

from cyguide.cli.context import (
    EXIT_MISSING_DEP,
    EXIT_SUCCESS,
    EXIT_USAGE_ERROR,
    CliContext,
)
from cyguide.cli.formatters import (
    print_error,
    print_info,
    print_json,
    print_success,
    print_table,
)
from cyguide.engine.adapter import clear_binary_cache


def handle_tool(args: Any, context: CliContext) -> int:
    """Route tool subcommands."""
    subaction = getattr(args, "tool_action", None)
    if not subaction:
        print_error("Missing tool action. Use: list, check, or info.")
        return EXIT_USAGE_ERROR

    registry = context.get_tool_registry()

    if subaction == "list":
        return _tool_list(registry, context)
    elif subaction == "check":
        return _tool_check(args, registry, context)
    elif subaction == "info":
        return _tool_info(args, registry, context)
    else:
        print_error(f"Unknown tool action: {subaction}")
        return EXIT_USAGE_ERROR


def _tool_list(registry, context: CliContext) -> int:
    """List all registered tools and their installation status."""
    tool_items = []
    for name, tool_data in sorted(registry.tools.items()):
        manifest = tool_data["manifest"]
        adapter = tool_data["adapter"]
        installed = adapter.validate_install()
        recipes = manifest.learning.recipes if manifest.learning else []
        recipes_count = len(recipes)
        version = getattr(manifest.meta, "version", "1.0.0")
        tool_items.append(
            {
                "name": name,
                "version": version,
                "description": manifest.meta.description,
                "binary": manifest.meta.binary,
                "installed": installed,
                "recipes_count": recipes_count,
            }
        )

    if context.is_json:
        print_json(tool_items)
        return EXIT_SUCCESS

    if not tool_items:
        print_info("No security tool plugins discovered.")
        return EXIT_SUCCESS

    rows = []
    for item in tool_items:
        status_str = "Installed" if item["installed"] else "Missing"
        rows.append(
            [
                item["name"],
                item["version"],
                item["binary"],
                status_str,
                str(item["recipes_count"]),
                item["description"][:45] + ("..." if len(item["description"]) > 45 else ""),
            ]
        )

    print_table(
        title="Discovered Security Tool Plugins",
        columns=[
            ("Tool", "cyan"),
            ("Version", "white"),
            ("Binary", "dim"),
            ("Status", "none"),
            ("Recipes", "yellow"),
            ("Description", "dim"),
        ],
        rows=rows,
    )
    return EXIT_SUCCESS


def _tool_check(args: Any, registry, context: CliContext) -> int:
    """Check binary availability for one or all tools. Returns 127 if missing."""
    clear_binary_cache()
    target_tool = getattr(args, "tool_name", None)

    tools_to_check = {}
    if target_tool:
        tool_data = registry.get_tool(target_tool)
        if not tool_data:
            print_error(f"Tool '{target_tool}' is not registered.")
            return EXIT_USAGE_ERROR
        tools_to_check[target_tool] = tool_data
    else:
        tools_to_check = registry.tools

    results = {}
    all_installed = True

    for name, data in sorted(tools_to_check.items()):
        adapter = data["adapter"]
        manifest = data["manifest"]
        installed = adapter.validate_install()
        results[name] = {
            "binary": manifest.meta.binary,
            "installed": installed,
        }
        if not installed:
            all_installed = False

    if context.is_json:
        print_json({"all_installed": all_installed, "tools": results})
        return EXIT_SUCCESS if all_installed else EXIT_MISSING_DEP

    rows = []
    for name, res in results.items():
        status_str = "Available" if res["installed"] else "Missing (127)"
        rows.append([name, res["binary"], status_str])

    print_table(
        title="Tool Binary Installation Check",
        columns=[
            ("Tool", "cyan"),
            ("Expected Binary", "white"),
            ("Status", "none"),
        ],
        rows=rows,
    )

    if not all_installed:
        print_error("One or more required tool binaries are missing from PATH.")
        return EXIT_MISSING_DEP

    print_success("All checked tool binaries are installed and available.")
    return EXIT_SUCCESS


def _tool_info(args: Any, registry, context: CliContext) -> int:
    """Display comprehensive metadata and recipes for a specific tool."""
    tool_name = args.tool_name
    tool_data = registry.get_tool(tool_name)
    if not tool_data:
        print_error(f"Tool '{tool_name}' not found.")
        return EXIT_USAGE_ERROR

    manifest = tool_data["manifest"]
    adapter = tool_data["adapter"]
    installed = adapter.validate_install()
    recipes = manifest.learning.recipes if manifest.learning else []

    accepts = manifest.input.get("accepts", []) if isinstance(manifest.input, dict) else []
    emits = manifest.output.get("emits", []) if isinstance(manifest.output, dict) else []

    info_dict = {
        "name": manifest.meta.name,
        "version": getattr(manifest.meta, "version", "1.0.0"),
        "description": manifest.meta.description,
        "binary": manifest.meta.binary,
        "installed": installed,
        "accepts": accepts,
        "emits": emits,
        "recipes": [r.model_dump() for r in recipes],
    }

    if context.is_json:
        print_json(info_dict)
        return EXIT_SUCCESS

    print_info(f"Tool: {manifest.meta.name} (v{getattr(manifest.meta, 'version', '1.0.0')})")
    print_info(f"Description: {manifest.meta.description}")
    print_info(
        f"Binary: {manifest.meta.binary} | Status: {'Installed' if installed else 'Missing'}"
    )
    print_info(f"Accepts: {', '.join(accepts) or 'None'}")
    print_info(f"Emits: {', '.join(emits) or 'None'}")

    recipe_rows = []
    for r in recipes:
        wire = (
            getattr(r.theory, "packet_wire_summary", r.description) if r.theory else r.description
        )
        flags_str = " ".join(r.flags) if r.flags else ""
        recipe_rows.append(
            [
                r.name,
                getattr(r, "difficulty", "Beginner"),
                flags_str,
                wire[:50],
            ]
        )

    print_table(
        title=f"Curriculum Recipes for {manifest.meta.name}",
        columns=[
            ("Recipe Name", "cyan"),
            ("Difficulty", "yellow"),
            ("Flags", "white"),
            ("Summary", "dim"),
        ],
        rows=recipe_rows,
    )
    return EXIT_SUCCESS
