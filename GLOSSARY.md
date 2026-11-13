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

