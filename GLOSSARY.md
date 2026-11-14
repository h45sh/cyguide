# CyGuide

A modular terminal cybersecurity investigation platform combining interactive tool execution, entity graph correlation, and learning guidance.

## Language

**Workspace**:
A top-level organization unit grouping related investigation sessions under an engagement target.
_Avoid_: Folder, project, target group

**Session**:
An immutable, persistent investigation timeline stored in SQLite containing graph entities, actions, and event history.
_Avoid_: Engagement, project, run, tab

**ExecutionSession**:
The active, in-memory runtime managing command execution lifecycles, privileged interaction, and output streams for a session.
_Avoid_: Job manager, runner, terminal instance, worker

**Finding**:
A structured, canonicalized unit of discovered security intelligence associated with an entity.
_Avoid_: Result, discovery, vulnerability (for generic data), raw output

**Action**:
An explicit, recorded invocation of a security tool or shell command triggered by an operator or autonomous agent.
_Avoid_: Job, task, subprocess, command run

**Primary Identity Key (PIK)**:
A deterministic set of identity attributes uniquely identifying a graph entity across different tool discoveries.
_Avoid_: Primary key, UUID, entity tag

**ExplanationTutor**:
The AI guidance and educational analysis subsystem providing contextual learning, vulnerability explication, and remediation advice.
_Avoid_: LLM client, AI assistant, chatbot, prompt runner

**WorkspaceRepository**:
The deep module managing persistent lifecycle operations, entity indexing, forensic archiving, and portability for Workspaces and Sessions.
_Avoid_: Workspace manager, session service, database helper, CRUD layer

**SessionReportService**:
The deep module managing forensic investigation reporting, Markdown table synthesis, Mermaid graph visualization, and secure file export.
_Avoid_: Reporter helper, markdown generator, export script

**ActionTimelineRepository**:
The deep module managing persistent event logging, audit trails, and active/closed tab status for investigation sessions.
_Avoid_: Event logger, audit store, timeline manager

**WorkspaceContextBuilder**:
The deep module responsible for compiling point-in-time snapshots of investigation context, resolving target entity variables, operator LHOST networking, and active job status.
_Avoid_: Context helper, context assembler, facade query

**DiagnosticEngine**:
The deep module managing environmental health auditing, tool availability checks, database integrity validation, and explainer connectivity probing.
_Avoid_: Diagnostics runner, health check script, test utility

