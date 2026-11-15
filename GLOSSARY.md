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
The active, in-memory runtime managing command execution lifecycles, privileged interaction, session eviction, and output streams for a session.
_Avoid_: Job manager, runner, terminal instance, worker

**ActionGateway**:
The deep module managing security boundary enforcement, cloud metadata SSRF defense, tool manifest input contract validation, and target variable interpolation.
_Avoid_: Validator, firewall, auth check, proxy

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

**PreferencesStore**:
The deep module managing persistent operator settings, active AI key profile configuration, and atomic scratchpad note-taking with NIST-compliant filesystem permission controls.
_Avoid_: Config helper, settings manager, json reader, file utility

**LearningSession**:
The deep module encapsulating interactive single-tool learning mode workflows: tool context resolution, recipe parameter binding, execution lifecycle orchestration, structured finding extraction, and AI educational tutoring behind an agnostic headless seam.
_Avoid_: Learning controller, learning screen backend, lesson helper, tutor runner

**RecipeBinding**:
The deep module resolving tool workflow recipes, flag parameter substitutions, target macros, and wordlist interpolations for security tools.
_Avoid_: Recipe parser, flag builder, command formatter

**InvestigationSession**:
The core seam governing investigation runtime environments (Learning & Power), standardizing action dispatch, stop controls, and structured reporting.
_Avoid_: Session interface, runtime controller, execution wrapper

**RecipeDeck**:
The deep presentation widget encapsulating tool metadata badges, status states, and interactive workflow recipe cards behind a declarative update interface.
_Avoid_: Recipe list view, card container, recipe scroller

**CommandPreviewEditor**:
The deep presentation adapter managing target and flag inputs while delegating real-time command syntax and macro resolution to RecipeBinding.
_Avoid_: Flag editor, parameter input box, command builder


