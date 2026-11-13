"""Specialized widgets for Power Mode."""

import asyncio
import json
import os
import re
import subprocess
from datetime import UTC, datetime
from typing import Any, Dict, List

from textual import events, work
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.geometry import Offset
from textual.widgets import Input, Label, ListItem, ListView, Static, Tree

from cyguide.schemas.power import JobStatus, JobStatusEnum


def _format_elapsed(seconds: float) -> str:
    secs = max(0, int(seconds))
    if secs < 60:
        return f"{secs:02d}s"
    mins, s = divmod(secs, 60)
    if mins < 60:
        return f"{mins:02d}m:{s:02d}s"
    hrs, m = divmod(mins, 60)
    return f"{hrs:02d}h:{m:02d}m:{s:02d}s"



class EntityBrowser(Tree):
    """Hierarchical browser for findings in the current session."""

    ALLOW_SELECT = False

    def __init__(self, **kwargs):
        super().__init__("ENTITY BROWSER", **kwargs)
        self.root.expand()
        self.filter_query: str = ""
        self._last_graph_data: Dict[str, Any] = {}

    @property
    def last_graph_data(self) -> Dict[str, Any]:
        """Cached entity graph data from the last refresh."""
        return self._last_graph_data

    def set_filter(self, query: str) -> None:
        """Update search filter and preserve query."""
        self.filter_query = (query or "").strip().lower()

    async def refresh_entities(self, graph_data: Dict[str, Any]):
        """Update the tree based on fresh nodes and edges from the store, preserving branch states."""
        self._last_graph_data = graph_data
        # Capture current expanded states if any
        expanded_keys = set()
        def collect_expanded(tree_node):
            if getattr(tree_node, "is_expanded", False):
                key = tree_node.data.get("id") if (tree_node.data and "id" in tree_node.data) else str(tree_node.label).split(" (")[0]
                expanded_keys.add(key)
            for child in getattr(tree_node, "children", []):
                collect_expanded(child)

        collect_expanded(self.root)

        self.clear()

        def should_expand(key: str, default: bool = True) -> bool:
            if self.filter_query:
                return True
            if not expanded_keys:
                return default
            return key in expanded_keys

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

        # Build IP-to-Name / Hostname / Alias mapping across all nodes and DNS records
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

        def get_label(node: Dict[str, Any]) -> str:
            st = node["schema_type"]
            pik = json.loads(node.get("pik_json", "{}"))
            data = json.loads(node.get("data_json", "{}"))
            custom_alias = data.get("alias")

            if st == "network.host":
                ip = pik.get("ip") or pik.get("host_ip") or node["id"][:8]
                hostname = custom_alias or data.get("hostname") or ip_to_name.get(ip)
                if ip in ("127.0.0.1", "::1") and not hostname:
                    hostname = "localhost"
                if hostname:
                    return f"{ip} ({hostname})"
                return ip
            elif st == "network.service":
                port = pik.get("port")
                protocol = pik.get("protocol", "tcp")
                base = f"{port}/{protocol}" if port else node["id"][:8]
                return f"{base} ({custom_alias})" if custom_alias else base
            elif st == "network.netblock":
                cidr = pik.get("cidr") or "Netblock"
                org = custom_alias or data.get("organization")
                if org and len(org) > 16:
                    org = org[:14] + "…"
                return f"{cidr} ({org})" if org else cidr
            elif st == "domain.info":
                dom = pik.get("domain", "Domain")
                reg = custom_alias or data.get("registrar") or data.get("organization")
                if reg and len(reg) > 16:
                    reg = reg[:14] + "…"
                return f"{dom} ({reg})" if reg else dom
            elif st == "dns.record":
                dom = pik.get("domain", "")
                rtype = pik.get("type", "DNS")
                val = pik.get("value", "")
                base = f"{dom} [{rtype} ❯ {val}]" if (val and val not in ("ANY", "unknown")) else f"{dom} [{rtype}]"
                return f"{base} ({custom_alias})" if custom_alias else base
            elif st == "tls.certificate":
                cn = custom_alias or data.get("common_name")
                return f"TLS: {cn}" if cn else f"TLS: {pik.get('fingerprint_sha256', node['id'][:8])[:16]}"
            elif st.startswith("web."):
                base = pik.get("url") or pik.get("path") or f"{node['id'][:8]}"
                return f"{base} ({custom_alias})" if custom_alias else base
            elif st.startswith("credential."):
                username = pik.get("username", "?")
                base = f"{username}:****"
                return f"{base} ({custom_alias})" if custom_alias else base
            elif st.startswith("vulnerability."):
                base = pik.get("vuln_id") or pik.get("cve_id") or pik.get("title") or node["id"][:8]
                return f"{base} ({custom_alias})" if custom_alias else base
            else:
                base = node["id"][:8]
                return f"{base} ({custom_alias})" if custom_alias else base

        def add_node_to_tree(parent_tree_node, node_id: str):
            node = node_map[node_id]
            label = get_label(node)
            child_ids = children_map.get(node_id, [])

            if child_ids:
                is_exp = should_expand(node_id, True)
                new_tree_node = parent_tree_node.add(label, data={"id": node_id, "type": node["schema_type"]}, expand=is_exp)
                for cid in child_ids:
                    add_node_to_tree(new_tree_node, cid)
            else:
                parent_tree_node.add_leaf(label, data={"id": node_id, "type": node["schema_type"]})

        if self.filter_query:
            q = self.filter_query
            matching_ids = set()
            for n in nodes:
                st = n.get("schema_type", "").lower()
                lbl = get_label(n).lower()
                pik = n.get("pik_json", "").lower()
                data = n.get("data_json", "").lower()
                extra_match = False
                if st == "network.host":
                    try:
                        nip = json.loads(n.get("pik_json", "{}")).get("ip", "")
                        if nip in ip_to_name and q in ip_to_name[nip].lower():
                            extra_match = True
                    except Exception:
                        pass

                if q in lbl or q in st or q in pik or q in data or extra_match:
                    matching_ids.add(n["id"])

            # Propagate upwards to keep ancestor nodes visible
            parent_map = {}
            for edge in edges:
                parent_map[edge["target_id"]] = edge["source_id"]

            to_check = list(matching_ids)
            for nid in to_check:
                curr = nid
                while curr in parent_map:
                    parent = parent_map[curr]
                    matching_ids.add(parent)
                    curr = parent

            nodes = [n for n in nodes if n["id"] in matching_ids]
            node_map = {n["id"]: n for n in nodes}
            children_map = {n["id"]: [c for c in children_map.get(n["id"], []) if c in matching_ids] for n in nodes}
            has_parent = {c for clist in children_map.values() for c in clist}

        if not nodes:
            if self.filter_query:
                self.root.add_leaf(f"[dim #94a3b8]No matches for '{self.filter_query}'[/]")
            else:
                self.root.add_leaf("[dim #94a3b8]No entities discovered yet[/]")
            return

        # Group root nodes by logical categories
        hosts = [n for n in nodes if n["id"] not in has_parent and n["schema_type"] == "network.host"]
        others = [n for n in nodes if n["id"] not in has_parent and n["schema_type"] != "network.host"]

        if hosts:
            hosts_root = self.root.add(f"Targets ({len(hosts)})", expand=should_expand("Targets", True))
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
            svc_root = self.root.add(f"Other Services ({len(services)})", expand=should_expand("Other Services", True))
            for s in services: add_node_to_tree(svc_root, s["id"])

        if domains_dns:
            dns_root = self.root.add(f"Domains & DNS ({len(domains_dns)})", expand=should_expand("Domains & DNS", True))
            for d in domains_dns: add_node_to_tree(dns_root, d["id"])

        if netblocks:
            net_root = self.root.add(f"Netblocks ({len(netblocks)})", expand=should_expand("Netblocks", True))
            for nb in netblocks: add_node_to_tree(net_root, nb["id"])

        if web:
            web_root = self.root.add(f"Web ({len(web)})", expand=should_expand("Web", True))
            for w in web: add_node_to_tree(web_root, w["id"])

        if creds:
            cred_root = self.root.add(f"Credentials ({len(creds)})", expand=should_expand("Credentials", True))
            for c in creds: add_node_to_tree(cred_root, c["id"])

        if vulns:
            vuln_root = self.root.add(f"Vulnerabilities ({len(vulns)})", expand=should_expand("Vulnerabilities", True))
            for v in vulns: add_node_to_tree(vuln_root, v["id"])

        if misc:
            misc_root = self.root.add(f"Other Entities ({len(misc)})", expand=should_expand("Other Entities", True))
            for m in misc: add_node_to_tree(misc_root, m["id"])


class JobQueue(Vertical):
    """Displays running and queued jobs."""

    class JobSelected(events.Event):
        """Emitted when a job is clicked in the list."""
        def __init__(self, job_id: str, session_id: str):
            super().__init__()
            self.job_id = job_id
            self.session_id = session_id

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._update_lock = asyncio.Lock()

    def compose(self) -> ComposeResult:
        yield ListView(id="power_job_list")

    async def update_jobs(self, jobs: List[JobStatus]):
        """Refresh the list of active jobs with live runtime and tab association."""
        async with self._update_lock:
            job_list = self.query_one("#power_job_list", ListView)
            old_idx = job_list.index

            if not jobs:
                current_first = job_list.children[0] if job_list.children else None
                if getattr(current_first, "id", None) != "empty_jobs":
                    await job_list.clear()
                    item = ListItem(Static("[dim #94a3b8]  No active jobs[/]"), disabled=True, id="empty_jobs")
                    job_list.append(item)
                return

            sorted_jobs = sorted(jobs, key=lambda j: (j.status == JobStatusEnum.RUNNING, j.started_at), reverse=True)
            now = datetime.now(UTC)

            seen_ids = set()
            new_items = []
            for job in sorted_jobs:
                jid_str = str(job.job_id)
                if jid_str in seen_ids:
                    continue
                seen_ids.add(jid_str)

                if job.status == JobStatusEnum.RUNNING:
                    status_icon = "[bold #34d399]◌[/]"
                    status_text = " [bold #34d399]RUNNING[/]"
                    elapsed = (now - job.started_at).total_seconds()
                elif job.status == JobStatusEnum.DONE:
                    status_icon = "[#64748b]●[/]"
                    status_text = " [dim #64748b]DONE[/]"
                    elapsed = ((job.completed_at or now) - job.started_at).total_seconds()
                elif job.status == JobStatusEnum.FAILED:
                    status_icon = "[#f85149]×[/]"
                    status_text = " [red]FAILED[/]"
                    elapsed = ((job.completed_at or now) - job.started_at).total_seconds()
                else: # QUEUED
                    status_icon = "[#eab308]◌[/]"
                    status_text = " [yellow]QUEUED[/]"
                    elapsed = (now - job.started_at).total_seconds()

                dur_str = f" [dim #94a3b8]{_format_elapsed(elapsed)}[/]"
                tab_str = f" [dim #38bdf8]\\[{job.tab_id}][/]" if job.tab_id else ""
                cmd = job.command_snippet or job.tool_name
                if len(cmd) > 20:
                    cmd = cmd[:19] + "…"

                label = f"  {status_icon}{tab_str} {cmd} [#64748b]{job.job_id.hex[:4]}[/]{dur_str}{status_text}"
                new_items.append((jid_str, str(job.session_id), label))

            # Check if items can be updated in place without clearing
            current_ids = [getattr(c, "job_id", None) for c in job_list.children]
            expected_ids = [item[0] for item in new_items]

            if current_ids == expected_ids:
                for i, (_, _, label) in enumerate(new_items):
                    try:
                        job_list.children[i].query_one(Static).update(label)
                    except Exception:
                        pass
            else:
                await job_list.clear()
                for j_id, s_id, label in new_items:
                    item = ListItem(Static(label))
                    item.job_id = j_id
                    item.session_id = s_id
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

    def _update_lhost_badge(self) -> None:
        try:
            from cyguide.engine.network import get_lhost_info
            ip, iface = get_lhost_info()
            badge = self.query_one("#lhost_badge", Label)
            is_vpn = iface.startswith(("tun", "wg", "tap", "ppp", "utun"))
            badge.set_class(is_vpn, "vpn")
            if is_vpn:
                badge.update(f"[{iface}: {ip}]")
            else:
                badge.update(f"[{iface}: {ip}]" if iface != "lo" else f"[LHOST: {ip}]")
        except Exception:
            pass

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
