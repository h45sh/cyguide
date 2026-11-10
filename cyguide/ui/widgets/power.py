"""Specialized widgets for Power Mode."""

import asyncio
import json
import os
import re
import subprocess
from typing import Dict, Any, List
from textual import events, work
from textual.widgets import Tree, Static, Label, ListView, ListItem, Input
from textual.containers import Vertical, Horizontal
from textual.geometry import Offset
from textual.app import ComposeResult
from cyguide.schemas.power import JobStatus, JobStatusEnum


class EntityBrowser(Tree):
    """Hierarchical browser for findings in the current session."""

    def __init__(self, **kwargs):
        super().__init__("ENTITY BROWSER", **kwargs)
        self.root.expand()

    async def refresh_entities(self, graph_data: Dict[str, Any]):
        """Update the tree based on fresh nodes and edges from the store."""
        self.clear()

        nodes = graph_data.get("nodes", [])
        edges = graph_data.get("edges", [])

        # Build node lookup map
        node_map = {n["id"]: n for n in nodes}

        # Build children map: parent_id -> list of child_ids
        children_map = {n["id"]: [] for n in nodes}
        # A set to keep track of nodes that have a parent (to identify roots)
        has_parent = set()

        for edge in edges:
            src = edge["source_id"]
            dst = edge["target_id"]
            if src in children_map and dst in node_map:
                children_map[src].append(dst)
                has_parent.add(dst)

        def get_label(node: Dict[str, Any]) -> str:
            st = node["schema_type"]
            pik = json.loads(node.get("pik_json", "{}"))
            data = json.loads(node.get("data_json", "{}"))

            if st == "network.host":
                return pik.get("ip") or pik.get("host_ip") or node["id"][:8]
            elif st == "network.service":
                port = pik.get("port")
                protocol = pik.get("protocol", "tcp")
                if port:
                    return f"{port}/{protocol}"
                return node["id"][:8]
            elif st == "network.netblock":
                cidr = pik.get("cidr") or "Netblock"
                org = data.get("organization")
                if org and len(org) > 16:
                    org = org[:14] + "…"
                return f"{cidr} ({org})" if org else cidr
            elif st == "domain.info":
                dom = pik.get("domain", "Domain")
                reg = data.get("registrar") or data.get("organization")
                if reg and len(reg) > 16:
                    reg = reg[:14] + "…"
                return f"{dom} ({reg})" if reg else dom
            elif st == "dns.record":
                dom = pik.get("domain", "")
                rtype = pik.get("type", "DNS")
                val = pik.get("value", "")
                if val and val not in ("ANY", "unknown"):
                    return f"{dom} [{rtype} ❯ {val}]"
                return f"{dom} [{rtype}]"
            elif st == "tls.certificate":
                cn = data.get("common_name")
                return f"TLS: {cn}" if cn else f"TLS: {pik.get('fingerprint_sha256', node['id'][:8])[:16]}"
            elif st.startswith("web."):
                return pik.get("url") or pik.get("path") or f"{node['id'][:8]}"
            elif st.startswith("credential."):
                username = pik.get("username", "?")
                return f"{username}:****"
            elif st.startswith("vulnerability."):
                return pik.get("vuln_id") or pik.get("cve_id") or pik.get("title") or node["id"][:8]
            else:
                return node["id"][:8]

        def add_node_to_tree(parent_tree_node, node_id: str):
            node = node_map[node_id]
            label = get_label(node)
            child_ids = children_map.get(node_id, [])

            if child_ids:
                new_tree_node = parent_tree_node.add(label, data={"id": node_id, "type": node["schema_type"]}, expand=True)
                for cid in child_ids:
                    add_node_to_tree(new_tree_node, cid)
            else:
                parent_tree_node.add_leaf(label, data={"id": node_id, "type": node["schema_type"]})

        if not nodes:
            self.root.add_leaf("[dim #94a3b8]No entities discovered yet[/]")
            return

        # Group root nodes by logical categories
        hosts = [n for n in nodes if n["id"] not in has_parent and n["schema_type"] == "network.host"]
        others = [n for n in nodes if n["id"] not in has_parent and n["schema_type"] != "network.host"]

        if hosts:
            hosts_root = self.root.add("Targets", expand=True)
            for h in hosts:
                add_node_to_tree(hosts_root, h["id"])

        services = [n for n in others if n["schema_type"] == "network.service"]
        web = [n for n in others if n["schema_type"].startswith("web.")]
        domains_dns = [n for n in others if n["schema_type"] in ("domain.info", "dns.record")]
        netblocks = [n for n in others if n["schema_type"] == "network.netblock"]
        creds = [n for n in others if n["schema_type"].startswith("credential.")]
        vulns = [n for n in others if n["schema_type"].startswith("vulnerability.")]
        categorized_ids = {n["id"] for n in (services + web + domains_dns + netblocks + creds + vulns)}
        misc = [n for n in others if n["id"] not in categorized_ids]

        if services:
            svc_root = self.root.add("Other Services", expand=True)
            for s in services: add_node_to_tree(svc_root, s["id"])

        if domains_dns:
            dns_root = self.root.add("Domains & DNS", expand=True)
            for d in domains_dns: add_node_to_tree(dns_root, d["id"])

        if netblocks:
            net_root = self.root.add("Netblocks", expand=True)
            for nb in netblocks: add_node_to_tree(net_root, nb["id"])

        if web:
            web_root = self.root.add("Web", expand=True)
            for w in web: add_node_to_tree(web_root, w["id"])

        if creds:
            cred_root = self.root.add("Credentials", expand=True)
            for c in creds: add_node_to_tree(cred_root, c["id"])

        if vulns:
            vuln_root = self.root.add("Vulnerabilities", expand=True)
            for v in vulns: add_node_to_tree(vuln_root, v["id"])

        if misc:
            misc_root = self.root.add("Other Entities", expand=True)
            for m in misc: add_node_to_tree(misc_root, m["id"])


class JobQueue(Vertical):
    """Displays running and queued jobs."""

    class JobSelected(events.Event):
        """Emitted when a job is clicked in the list."""
        def __init__(self, job_id: str, session_id: str):
            super().__init__()
            self.job_id = job_id
            self.session_id = session_id

    def compose(self) -> ComposeResult:
        yield ListView(id="power_job_list")

    async def update_jobs(self, jobs: List[JobStatus]):
        """Refresh the list of active jobs."""
        job_list = self.query_one("#power_job_list", ListView)
        old_idx = job_list.index

        await job_list.clear()

        if not jobs:
            job_list.append(ListItem(Static("[dim #94a3b8]  No active jobs[/]"), disabled=True))
            return

        sorted_jobs = sorted(jobs, key=lambda j: (j.status == JobStatusEnum.RUNNING, j.started_at), reverse=True)
        for job in sorted_jobs:
            if job.status == JobStatusEnum.RUNNING:
                status_icon = "[bold #34d399]◌[/]"
                status_text = " [bold #34d399]RUNNING[/]"
            elif job.status == JobStatusEnum.DONE:
                status_icon = "[#64748b]●[/]"
                status_text = ""
            elif job.status == JobStatusEnum.FAILED:
                status_icon = "[#f85149]×[/]"
                status_text = " [red]FAILED[/]"
            else: # QUEUED
                status_icon = "[#eab308]◌[/]"
                status_text = " [yellow]QUEUED[/]"

            label = f"  {status_icon} {job.tool_name} [#64748b]{job.job_id.hex[:4]}[/]{status_text}"
            item = ListItem(Static(label))
            item.job_id = str(job.job_id)
            item.session_id = str(job.session_id)
            job_list.append(item)

        if old_idx is not None and old_idx < len(job_list.children):
            job_list.index = old_idx


    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Handle job selection in the queue."""
        if hasattr(event.item, "job_id") and hasattr(event.item, "session_id"):
            self.post_message(self.JobSelected(event.item.job_id, event.item.session_id))


class CommandPalette(Vertical):
    """The interactive command prompt with Gemini-CLI style metrics."""

    can_focus = False

    @property
    def allow_vertical_scroll(self) -> bool:
        return False

    @property
    def allow_horizontal_scroll(self) -> bool:
        return False

    def _scroll_to(self, *args, **kwargs) -> bool:
        return False

    def scroll_to(self, *args, **kwargs) -> None:
        pass

    def scroll_relative(self, *args, **kwargs) -> None:
        pass

    def scroll_to_region(self, *args, **kwargs) -> Offset:
        return Offset(0, 0)

    def scroll_to_widget(self, *args, **kwargs) -> bool:
        return True

    class Submitted(Input.Submitted):
        """Event emitted when a command is submitted."""
        def __init__(self, command: str, tool_name: str, expanded_params: List[str], input: Input, is_manual_shell: bool = False, new_tab: bool = False):
            super().__init__(input, command)
            self.tool_name = tool_name
            self.expanded_params = expanded_params
            self.is_manual_shell = is_manual_shell
            self.new_tab = new_tab

    class ShowShortcutsRequest(events.Event):
        """Request to show the shortcuts help dialog."""
        pass

    class CloseTabRequest(events.Event):
        """Request to close the active tab."""
        pass

    class KillJobRequest(events.Event):
        """Request to kill the job in the active tab."""
        pass

    class ExportRequest(events.Event):
        """Request to export the session."""
        pass

    class NextSessionRequest(events.Event):
        """Request to switch to the next session."""
        pass

    class PrevSessionRequest(events.Event):
        """Request to switch to the previous session."""
        pass

    class CopyTabRequest(events.Event):
        """Request to copy active tab log to clipboard."""
        pass

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.resolved_vars: Dict[str, Any] = {}
        self.history: List[str] = []
        self.history_index: int = -1
        self.shell_locked: bool = False
        self._force_new_tab: bool = False
        self.cwd = os.getcwd()
        self.branch = ""

    def _get_git_branch(self) -> str:
        try:
            return subprocess.check_output(
                ["git", "branch", "--show-current"],
                stderr=subprocess.DEVNULL
            ).decode().strip()
        except Exception:
            return ""

    @work(exclusive=True, group="git_branch")
    async def _async_update_git_branch(self) -> None:
        try:
            branch = await asyncio.to_thread(self._get_git_branch)
            self.branch = branch
        except Exception:
            self.branch = ""

    def _update_lhost_badge(self, force_refresh: bool = False) -> None:
        try:
            from cyguide.engine.network import get_lhost_info
            ip, iface = get_lhost_info(force_refresh=force_refresh)
            badge = self.query_one("#lhost_badge", Label)
            is_vpn = iface.startswith(("tun", "wg", "tap", "ppp", "utun"))
            badge.set_class(is_vpn, "vpn")
            if is_vpn:
                badge.update(f"[{iface}: {ip}]")
            else:
                badge.update(f"[{iface}: {ip}]" if iface != "lo" else f"[LHOST: {ip}]")
        except Exception:
            pass

    def on_click(self, event) -> None:
        target = getattr(event, "target", None)
        if target and getattr(target, "id", None) == "lhost_badge":
            event.stop()
            if hasattr(self.app, "action_toggle_demo_mode"):
                self.app.action_toggle_demo_mode()
            else:
                if os.environ.get("CYGUIDE_DEMO", "").lower() in ("1", "true", "yes", "on"):
                    os.environ.pop("CYGUIDE_DEMO", None)
                    os.environ.pop("CYGUIDE_DUMMY_IP", None)
                else:
                    os.environ["CYGUIDE_DEMO"] = "1"
                self._update_lhost_badge(force_refresh=True)

    def on_mount(self) -> None:
        self._async_update_git_branch()
        self._update_lhost_badge()

    def compose(self) -> ComposeResult:
        with Horizontal(id="palette_header"):
            with Horizontal(id="palette_header_left"):
                yield Label("● Tool Mode (! for shell)", id="mode_status")
                yield Label("[SHELL LOCK: OFF]", id="lock_icon")
                yield Label("[LHOST: -]", id="lhost_badge")
                yield Label("pwd:", classes="pwd_label")
                yield Label("~", id="pwd_line")
            yield Label("│", id="palette_header_sep")
            yield Label("F1 Help · Ctrl+T New Tab · Esc Dashboard", id="shortcuts_hint")
        yield Input(value="> ", placeholder="Enter command (e.g. nmap -sV target or !ls)...", id="command_input")
        yield Label("", id="context_line", classes="hidden")

    def update_context(self, resolved_vars: Dict[str, Any], is_registered_tool: bool = True, cwd: str = ""):
        """Update the prompt metrics showing path and git branch."""
        self.resolved_vars = resolved_vars
        self.cwd = cwd
        self._async_update_git_branch()

        # Update metrics with middle/tail truncation to prevent header collision
        short_path = cwd.replace(os.path.expanduser("~"), "~")
        if len(short_path) > 22:
            short_path = "..." + short_path[-19:]
        self.query_one("#pwd_line", Label).update(short_path)

        # Update lock label (showing explicit setting ON/OFF)
        lock_label = self.query_one("#lock_icon", Label)
        if self.shell_locked:
            lock_label.update("[SHELL LOCK: ON]")
            lock_label.set_class(True, "locked")
        else:
            lock_label.update("[SHELL LOCK: OFF]")
            lock_label.set_class(False, "locked")

        # Update Context Line
        context_label = self.query_one("#context_line", Label)
        if resolved_vars:
            context_str = " | ".join(f"${k}={v}" for k, v in resolved_vars.items())
            context_label.update(f"Context: {context_str}")
            context_label.remove_class("hidden")
            self.set_class(True, "has-context")
        else:
            context_label.add_class("hidden")
            self.set_class(False, "has-context")

        # Update mode status based on current input and shell_locked
        self._update_mode_label()
        self._update_lhost_badge()

    def _update_mode_label(self):
        mode_label = self.query_one("#mode_status", Label)
        cmd_input = self.query_one("#command_input", Input)

        if self.shell_locked:
            mode_label.update("● Shell Locked (ctrl+l)")
            mode_label.set_class(True, "shell-mode")
        elif cmd_input.value.startswith("!"):
            mode_label.update("● Shell Mode (!)")
            mode_label.set_class(True, "shell-mode")
        else:
            mode_label.update("● Tool Mode (! for shell)")
            mode_label.set_class(False, "shell-mode")

    def on_key(self, event: events.Key) -> None:
        """Handle Up/Down arrows, '!' shortcut, Tab completion, and Tab management shortcuts."""
        cmd_input = self.query_one("#command_input", Input)

        # Intercept shortcuts that Input normally consumes
        if event.key == "f1":
            event.stop()
            event.prevent_default()
            self.post_message(self.ShowShortcutsRequest())
            return
        elif event.key == "ctrl+w":
            event.stop()
            event.prevent_default()
            self.post_message(self.CloseTabRequest())
            return
        elif event.key == "ctrl+y":
            event.stop()
            event.prevent_default()
            self.post_message(self.CopyTabRequest())
            return
        elif event.key == "ctrl+k":
            event.stop()
            event.prevent_default()
            self.post_message(self.KillJobRequest())
            return
        elif event.key == "ctrl+e":
            event.stop()
            event.prevent_default()
            self.post_message(self.ExportRequest())
            return
        elif event.key == "ctrl+right":
            event.stop()
            event.prevent_default()
            self.post_message(self.NextSessionRequest())
            return
        elif event.key == "ctrl+left":
            event.stop()
            event.prevent_default()
            self.post_message(self.PrevSessionRequest())
            return

        elif event.key in ("shift+enter", "alt+enter", "ctrl+j"):
            self._force_new_tab = True
            asyncio.create_task(cmd_input.action_submit())
            event.stop()
            event.prevent_default()
            return

        # '!' shortcut: Toggle prefix
        if event.character == "!" and not self.shell_locked:
            if not cmd_input.has_focus:
                event.stop()
                event.prevent_default()
                cmd_input.focus()
            return

        # Tab completion in Locked mode
        if event.key == "tab" and self.shell_locked:
            event.stop()
            event.prevent_default()
            self._handle_tab_completion(cmd_input)
            return

        if event.key == "up":
            if self.history and self.history_index < len(self.history) - 1:
                self.history_index += 1
                cmd_input.value = self.history[-(self.history_index + 1)]
                cmd_input.cursor_position = len(cmd_input.value)
        elif event.key == "down":
            if self.history_index > 0:
                self.history_index -= 1
                cmd_input.value = self.history[-(self.history_index + 1)]
                cmd_input.cursor_position = len(cmd_input.value)
            elif self.history_index == 0:
                self.history_index = -1
                mode_label = self.query_one("#mode_status", Label)
                cmd_input.value = "! " if mode_label.has_class("shell-mode") else "> "
                cmd_input.cursor_position = 2

    def _handle_tab_completion(self, cmd_input: Input) -> None:
        """Simple filename completion for the current CWD."""
        if not self.cwd or not os.path.isdir(self.cwd):
            return

        val = cmd_input.value
        pos = cmd_input.cursor_position

        # Find the word being typed
        before_cursor = val[:pos]
        parts = before_cursor.split()
        if not parts:
            return

        last_word = parts[-1]

        try:
            # List files in CWD
            files = os.listdir(self.cwd)
            matches = [f for f in files if f.startswith(last_word)]

            if len(matches) == 1:
                # Complete the word
                completion = matches[0][len(last_word):]
                cmd_input.value = before_cursor + completion + val[pos:]
                cmd_input.cursor_position = pos + len(completion)
            elif len(matches) > 1:
                # Find common prefix
                common = os.path.commonprefix(matches)
                if len(common) > len(last_word):
                    completion = common[len(last_word):]
                    cmd_input.value = before_cursor + completion + val[pos:]
                    cmd_input.cursor_position = pos + len(completion)
        except Exception:
            pass

    def on_input_changed(self, event: Input.Changed) -> None:
        """Ensure the prefix (> or !) is never deleted and handle pattern-based toggles."""
        val = event.value

        # 1. Pattern-based mode toggle (ONLY if it's the only character after prefix)
        if val == "> !":
            event.input.value = "! "
            event.input.cursor_position = 2
            self._update_mode_label()
            return
        elif val == "! !":
            event.input.value = "> "
            event.input.cursor_position = 2
            self._update_mode_label()
            return

        # Redundant multiple prefix protection: e.g. "> >", "! !", "> !", "! >", ">>", "!!"
        if val.startswith(("> >", "! !", "> !", "! >", ">>", "!!")):
            active_prefix = "! " if (self.shell_locked or val.startswith("!")) else "> "
            clean_tail = val.lstrip(">! ")
            event.input.value = active_prefix + clean_tail
            event.input.cursor_position = len(event.input.value)
            self._update_mode_label()
            return

        # 2. Prefix protection: Ensure prefix is never deleted
        expected_prefix = "! " if self.shell_locked else "> "
        if not (val.startswith(">") or val.startswith("!")):
            event.input.value = expected_prefix + val.lstrip()
            event.input.cursor_position = len(event.input.value)

        self._update_mode_label()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Intercept input and bubble a custom event."""
        event.stop()
        raw_cmd = event.value.strip()
        if not raw_cmd:
            return

        # Record History
        if not self.history or self.history[-1] != raw_cmd:
            self.history.append(raw_cmd)
        self.history_index = -1

        # Determine mode from prefix
        is_manual_shell = raw_cmd.startswith("!") or self.shell_locked

        # Strip all leading prefix symbols (> or !) and whitespace
        clean_cmd = re.sub(r'^[>!\s]+', '', raw_cmd).strip()

        if not clean_cmd:
            event.input.value = "! " if is_manual_shell and not self.shell_locked else "> "
            return

        parts = clean_cmd.split()
        if not parts: return
        tool_name = parts[0]
        params_str = clean_cmd[len(tool_name):].strip()

        # Clear input and restore the active prefix (sticky mode)
        event.input.value = "! " if is_manual_shell and not self.shell_locked else "> "
        if self.shell_locked:
            event.input.value = "! "

        # The screen will handle the rejection if tool_name is not registered and ! wasn't used
        self.post_message(self.Submitted(clean_cmd, tool_name, [params_str], event.input, is_manual_shell, new_tab=self._force_new_tab))
        self._force_new_tab = False
