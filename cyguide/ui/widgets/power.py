"""Specialized widgets for Power Mode."""

import json
import os
import subprocess
from typing import Dict, Any, List, Optional
from textual import events
from textual.widgets import Tree, Static, Label, ListView, ListItem, Input, Rule
from textual.containers import Vertical, Horizontal
from textual.app import ComposeResult
from cyguide.schemas.power import JobStatus, JobStatusEnum
from cyguide.schemas.base import BaseFinding


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
                return f"{cidr} ({org})" if org else cidr
            elif st == "domain.info":
                dom = pik.get("domain", "Domain")
                reg = data.get("registrar") or data.get("organization")
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
        yield Label("JOB QUEUE", classes="section_header")
        yield ListView(id="power_job_list")

    async def update_jobs(self, jobs: List[JobStatus]):
        """Refresh the list of active jobs."""
        job_list = self.query_one("#power_job_list", ListView)
        old_idx = job_list.index
        
        await job_list.clear()
        
        # Group by session_id
        session_groups = {}
        for job in jobs:
            session_groups.setdefault(str(job.session_id), []).append(job)

        for session_id, s_jobs in session_groups.items():
            header = ListItem(Label(f"Session {session_id[:8]}", classes="section_header"))
            job_list.append(header)
            
            sorted_jobs = sorted(s_jobs, key=lambda j: (j.status == JobStatusEnum.RUNNING, j.started_at), reverse=True)
            for job in sorted_jobs:
                if job.status == JobStatusEnum.RUNNING:
                    status_icon = "◯"
                    style = "bold #58a6ff"
                elif job.status == JobStatusEnum.DONE:
                    status_icon = "●"
                    style = "#3fb950"
                elif job.status == JobStatusEnum.FAILED:
                    status_icon = "×"
                    style = "#f85149"
                else: # QUEUED
                    status_icon = "⚪"
                    style = "#8b949e"
                
                label = f"  {status_icon} {job.tool_name} [#8b949e]{job.job_id.hex[:4]}[/]"
                item = ListItem(Static(label), id=f"job_item_{job.job_id.hex}")
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

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.resolved_vars: Dict[str, Any] = {}
        self.cwd: str = ""
        self.branch: str = ""
        self.history: List[str] = []
        self.history_index: int = -1
        self.shell_locked: bool = False
        self._force_new_tab: bool = False
        self.cwd = os.getcwd()
        self.branch = self._get_git_branch()

    def _get_git_branch(self) -> str:
        try:
            return subprocess.check_output(
                ["git", "branch", "--show-current"], 
                stderr=subprocess.DEVNULL
            ).decode().strip()
        except Exception:
            return ""

    def compose(self) -> ComposeResult:
        with Horizontal(id="palette_header"):
            yield Label("Tool Mode (press ! for shell)", id="mode_status")
            yield Static("", expand=True)
            yield Label("", id="lock_icon")
            yield Label("F1 or Ctrl+/ for shortcuts", id="shortcuts_hint")
        
        yield Rule(classes="minimal-sep")
        yield Input(value="> ", id="command_input")
        with Horizontal(id="pwd_container"):
            yield Label("pwd:", classes="pwd_label")
            yield Label("~", id="pwd_line")
        yield Rule(classes="minimal-sep")
        
        yield Label("", id="context_line", classes="hidden")
        yield Label("", id="status_line", classes="hidden")

    def show_status(self, message: str, severity: str = "info") -> None:
        """Removed as per user request for absolute minimalism."""
        pass

    def update_context(self, resolved_vars: Dict[str, Any], is_registered_tool: bool = True, cwd: str = ""):
        """Update the prompt metrics showing path and git branch."""
        self.resolved_vars = resolved_vars
        self.cwd = cwd
        self.branch = self._get_git_branch()
        
        # Update metrics
        short_path = cwd.replace(os.path.expanduser("~"), "~")
        self.query_one("#pwd_line", Label).update(short_path)
        
        # Update lock icon
        lock_label = self.query_one("#lock_icon", Label)
        if self.shell_locked:
            lock_label.update("🔒 ")
        else:
            lock_label.update("")
            
        # Update Context Line
        context_label = self.query_one("#context_line", Label)
        if resolved_vars:
            context_str = " | ".join(f"${k}={v}" for k, v in resolved_vars.items())
            context_label.update(f"Context: {context_str}")
            context_label.remove_class("hidden")
        else:
            context_label.add_class("hidden")

        # Update mode status based on current input and shell_locked
        self._update_mode_label()

    def _update_mode_label(self):
        mode_label = self.query_one("#mode_status", Label)
        cmd_input = self.query_one("#command_input", Input)
        
        if self.shell_locked:
            mode_label.update("Shell Locked (ctrl+l to unlock)")
            mode_label.set_class(True, "shell-mode")
        elif cmd_input.value.startswith("!"):
            mode_label.update("Shell Mode (press ! to revert)")
            mode_label.set_class(True, "shell-mode")
        else:
            mode_label.update("Tool Mode (press ! for shell)")
            mode_label.set_class(False, "shell-mode")

    def on_key(self, event: events.Key) -> None:
        """Handle Up/Down arrows, '!' shortcut, Tab completion, and Tab management shortcuts."""
        cmd_input = self.query_one("#command_input", Input)
        
        # Intercept shortcuts that Input normally consumes
        if event.key in ("f1", "ctrl+slash", "ctrl+underscore"):
            event.stop()
            event.prevent_default()
            self.post_message(self.ShowShortcutsRequest())
            return
        elif event.key == "ctrl+w":
            event.stop()
            event.prevent_default()
            self.post_message(self.CloseTabRequest())
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
            cmd_input.action_submit()
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
        
        # Strip prefix for completion logic
        clean_val = val.lstrip(">! ")
        prefix_len = len(val) - len(clean_val)
        
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

        # 2. Prefix protection
        if not (val.startswith(">") or val.startswith("!")):
            # User deleted prefix, restore default
            event.input.value = "> " + val.lstrip()
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
        is_manual_shell = raw_cmd.startswith("!")
        if self.shell_locked:
            is_manual_shell = True
            
        # Strip prefix
        clean_cmd = raw_cmd[1:].strip()
        if not clean_cmd:
            event.input.value = "! " if is_manual_shell and not self.shell_locked else "> "
            return

        parts = clean_cmd.split()
        if not parts: return
        tool_name = parts[0]
        params_str = " ".join(parts[1:])

        # Clear input and restore the active prefix (sticky mode)
        event.input.value = "! " if is_manual_shell and not self.shell_locked else "> "
        if self.shell_locked:
            event.input.value = "! "

        # The screen will handle the rejection if tool_name is not registered and ! wasn't used
        self.post_message(self.Submitted(clean_cmd, tool_name, [params_str], event.input, is_manual_shell, new_tab=self._force_new_tab))
        self._force_new_tab = False


class SuggestionsPane(Vertical):
    """Displays AI/Rule proposed findings for operator review."""

    class Approved(events.Event):
        """Emitted when a suggestion is approved."""
        def __init__(self, schema_type: str, pik: Dict[str, Any], recommended_command: str):
            super().__init__()
            self.schema_type = schema_type
            self.pik = pik
            self.recommended_command = recommended_command

    class Dismissed(events.Event):
        """Emitted when a suggestion is dismissed."""
        def __init__(self, schema_type: str, pik: Dict[str, Any]):
            super().__init__()
            self.schema_type = schema_type
            self.pik = pik

    def compose(self) -> ComposeResult:
        yield Label("SUGGESTIONS", classes="section_header")
        yield ListView(id="power_suggestions_list")

    async def update_suggestions(self, suggestions: List[BaseFinding]):
        """Refresh the list of proposed findings."""
        suggest_list = self.query_one("#power_suggestions_list", ListView)
        old_idx = suggest_list.index
        
        await suggest_list.clear()
        
        for idx, sug in enumerate(suggestions):
            cmd = sug.data.get("recommended_command", "")
            tool = sug.data.get("tool_suggestion", "tool")
            
            # Label showing what tool and what target
            target_str = sug.pik.get("url") or sug.pik.get("ip") or sug.pik.get("host_ip") or "target"
            display_label = f"💡 {tool} ❯ {target_str}"
            
            item = ListItem(Static(display_label), id=f"sug_item_{idx}")
            item.schema_type = sug.schema_type
            item.pik = sug.pik
            item.recommended_command = cmd
            suggest_list.append(item)
            
        if old_idx is not None and old_idx < len(suggest_list.children):
            suggest_list.index = old_idx

    def on_key(self, event: events.Key) -> None:
        """Handle enter to approve and d/x/delete to dismiss."""
        suggest_list = self.query_one("#power_suggestions_list", ListView)
        idx = suggest_list.index
        if idx is None or idx >= len(suggest_list.children):
            return

        item = suggest_list.children[idx]
        # Ignore list header list items (if any are headers)
        if not hasattr(item, "recommended_command"):
            return

        if event.key in ("d", "delete", "x"):
            event.stop()
            event.prevent_default()
            self.post_message(self.Dismissed(item.schema_type, item.pik))

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Handle suggestion selection (click or enter key)."""
        item = event.item
        if item and hasattr(item, "recommended_command"):
            self.post_message(self.Approved(item.schema_type, item.pik, item.recommended_command))
