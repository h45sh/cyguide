# CyGuide Domain Context

This document defines the core domain concepts and terminology for CyGuide, a TUI-based guided cybersecurity learning platform.

## Core Concepts

### Finding
The primary unit of data in CyGuide. A finding is a structured object (e.g., `network.host`, `network.service`) emitted by a [Tool Adapter](#tool-adapter). Every finding must conform to a [Schema](#schema).

### Schema
A formal definition of a [Finding](#finding) type. It defines the required fields, [Primary Identity Keys (PIKs)](#primary-identity-key-pik), and structural relationships ([Parent](#parent-relation) or [Association](#association-relation)) used by the engine to wire the [Entity Graph](#entity-graph).

### Primary Identity Key (PIK)
A set of fields within a [Schema](#schema) that uniquely identifies an entity (e.g., `ip` for a host). The engine uses PIKs to perform **Upserts**—merging new data into existing entities instead of creating duplicates.

### Workspace
A high-level container representing a project or engagement (e.g., "Internal Audit 2024"). A workspace holds multiple [Sessions](#session) and tracks project-level metadata.

### Session
A specific thread of activity within a [Workspace](#workspace). 
- **Power Session**: A persistent, graph-backed investigation. Findings discovered in a Power Session are stored in a dedicated [Entity Graph](#entity-graph).
- **Learning Session**: An ephemeral, guided experience focused on a specific tool. Learning Sessions do not persist findings to the Entity Graph and are isolated from Workspace data.

### Entity Graph
A stateful, unified map of the target environment for a specific [Session](#session). It represents the "current truth" of that session, built by linking [Findings](#finding) together based on their [Schemas](#schema).

### Event Log
An append-only, immutable record of every [Finding](#finding) emitted. It serves as the **Reproducibility Foundation**; the [Entity Graph](#entity-graph) must be fully reconstructible by replaying the Event Log, ensuring session portability and auditing.

### Entity Alias
A first-class [Finding](#finding) that establishes an explicit link between two semantically identical but syntactically different identifiers (e.g., mapping a Hostname to an IP). Aliases prevent [Canonicalization](#canonicalization) from making semantic guesses.

### Tool Plugin
A self-contained directory in `tools/` consisting of:
- **Manifest**: A declarative `toml` file defining metadata, inputs, and outputs.
- **Tool Adapter**: A Python module implementing the logic to run the tool and parse its output.

### Tool Registry
The component responsible for discovering [Tool Plugins](#tool-plugin), validating [Manifests](#manifest), and rendering contextual suggestions in the TUI.

### Canonicalization
The process of normalizing raw data (e.g., lowercasing hex hashes, stripping whitespace) before it enters the [Graph Store](#graph-store). Canonicalization is strictly **syntactic**; semantic merging is handled via [Entity Aliases](#entity-alias).

## Relationships

### Parent Relation
A structural, lifecycle-bound link. Deleting a parent cascades to its children (e.g., a `network.service` belongs to a `network.host`).

### Association Relation
A semantic link between independent entities. These are non-structural edges (e.g., a `credential.found` is associated with the `web.endpoint` where it was leaked).

## Execution Modes

### Learning Mode
A guided operational mode using [Manifest](#manifest) metadata to provide step-by-step instructions and [First-Principle Explanations](#first-principle-explanation).

### Power Mode
A professional workspace featuring:
- **Strict Suggestions**: Tools are suggested only if they explicitly accept the selected entity's [Schema](#schema).
- **Derived Suggestions**: Manifest-declared inputs that allow tools to accept related entities (e.g., a web tool accepting a service) using **Declarative Filters** (`eq`, `in`, `contains`, `exists`).
- **Manual Override with Field Resolution**: Allows users to force-run any tool by explicitly providing the required parameters that the current entity lacks.

## Technical Terms

### TUI (Terminal User Interface)
The interactive user interface of CyGuide, built with the Textual framework.

### Graph Store
The persistence layer (SQLite) that manages the [Entity Graph](#entity-graph) and the [Event Log](#event-log).
