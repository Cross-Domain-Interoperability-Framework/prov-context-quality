# Agents in CDIF Provenance: Representation Across Vocabularies

**Date:** 2026-03-11
**Status:** Draft for review

## 1. Overview

Agents — the people, organizations, and software/machines that perform or are responsible for activities — are a core concept in provenance. Every provenance vocabulary used in CDIF represents agents, but each takes a different approach to typing, role assignment, and the relationship between agents and activities. These differences have practical consequences for implementers and for interoperability between vocabularies.

This document compares agent representation across the CDIF provenance building blocks (cdifProv, provActivity, ddicdiProv), the Dagstuhl Workshop PROV classes, and the external RO-Crate profiles (WRROC, ARC). It identifies areas of alignment and tension, and recommends a consistent approach for CDIF implementations.

## 2. The PROV Information Model for Agents

The W3C PROV Data Model ([PROV-DM](https://www.w3.org/TR/prov-dm/)) defines three core concepts:

- **Entity**: a physical, digital, conceptual, or other kind of thing
- **Activity**: something that occurs over a period of time and acts upon or with entities
- **Agent**: something that bears some form of responsibility for an activity taking place

Key design decisions in PROV:
- An Agent can *also* be an Entity (e.g., a Person is both an Agent when they act and an Entity when they are described)
- The simple relationship is `Activity --prov:wasAssociatedWith--> Agent`
- Roles are expressed through **qualified associations**: `Activity --prov:qualifiedAssociation--> Association --prov:agent--> Agent, --prov:hadRole--> Role`
- Agent subtypes defined by PROV: `prov:Person`, `prov:Organization`, `prov:SoftwareAgent`

## 3. Agent Representation in CDIF Building Blocks

### 3.1 cdifProv (schema.org + PROV-O)

cdifProv uses `schema:agent` as the primary property linking an activity to its responsible agent. This follows the schema.org Action model where `agent` is a direct property on the Action.

**Properties:**
- `schema:agent` — the primary responsible agent (singular)
- `schema:participant` — other participants in the activity (array)

**Accepted agent types:**
- `schema:Person` — individual contributor with name, ORCID, affiliation, contact
- `schema:Organization` — institutional contributor with name, identifier, type classification
- `schema:Role` (AgentInRole) — wraps a Person or Organization with a `schema:roleName`, using `schema:contributor` to point to the actual agent
- `@id` reference — pointer to an agent defined elsewhere in the document

**Example (Person):**
```json
"schema:agent": {
    "@type": "schema:Person",
    "schema:name": "Dr. Maria Chen",
    "schema:identifier": {
        "@type": "schema:PropertyValue",
        "schema:propertyID": "https://registry.identifiers.org/registry/orcid",
        "schema:value": "0000-0002-8765-4321",
        "schema:url": "https://orcid.org/0000-0002-8765-4321"
    },
    "schema:contactPoint": {"@id": "mailto:maria.chen@unr.edu"}
}
```

**Example (AgentInRole):**
```json
"schema:agent": {
    "@type": "schema:Role",
    "schema:roleName": "Principal Investigator",
    "schema:contributor": {
        "@type": "schema:Person",
        "schema:name": "Dr. Maria Chen"
    }
}
```

**Design rationale:** Schema.org's `agent` property is well-understood by web consumers. The AgentInRole pattern (using `schema:Role` as a wrapper) handles qualified roles without requiring PROV-O's more complex `qualifiedAssociation` mechanism. The `schema:participant` array accommodates additional agents without overloading the primary `schema:agent`.

### 3.2 provActivity (PROV-O first)

provActivity uses `prov:wasAssociatedWith` as the primary agent relationship, following canonical PROV-O.

**Properties:**
- `prov:wasAssociatedWith` — the agent(s) associated with the activity

**Accepted agent types:**
- `schema:Person` (inline, with schema.org properties for name, identifier, etc.)
- `schema:Organization` (inline)
- `@id` reference

**Design rationale:** Uses the PROV-O native relationship. Falls back to schema.org types for the agent description itself because PROV-O defines `prov:Person`, `prov:Organization`, and `prov:SoftwareAgent` as types but provides no properties for describing them (no name, identifier, contact properties in the PROV-O vocabulary).

Note: provActivity does *not* currently implement `prov:qualifiedAssociation` for role-bearing agents, deferring this to a future extension. This means roles cannot be expressed in provActivity without falling back to the cdifProv AgentInRole pattern.

### 3.3 ddicdiProv (DDI-CDI)

ddicdiProv uses a fundamentally different pattern: the agent-activity relationship is **inverted**.

**Properties:**
- `cdi:ProcessingAgent` — a separate graph node
- `cdi:performs` — points *from* the agent *to* the activity (agent → activity, not activity → agent)
- `cdi:operatesOn` → `cdi:ProductionEnvironment` — where the agent runs

**Agent structure:**
```json
{
    "@type": "cdi:ProcessingAgent",
    "@id": "#agent-lab",
    "cdi:name": { ... },
    "cdi:performs": [{"@id": "#activity-analysis"}],
    "cdi:operatesOn": [{"@id": "#env-lab"}]
}
```

**Design rationale:** DDI-CDI models `ProcessingAgent` as an independent entity with its own lifecycle. The inverted relationship (`agent performs activity`) reflects DDI-CDI's class-centric design where agents are first-class nodes that can be shared across activities and environments.

**Challenge:** This inversion is counterintuitive for most implementers and breaks the pattern used by every other vocabulary in the CDIF ecosystem. It means agents cannot be simply nested within activity nodes — they must be separate graph entities with cross-references.

## 4. Agents in the Dagstuhl Workshop PROV Classes

The [PROV_Classes.ttl](PROV_Classes.ttl) file captures a proposed provenance ontology discussed at the Dagstuhl Workshop (November 2025). Its agent model departs from the approach used in other CDIF vocabularies and raises important implementation questions.

### 4.1 The Proposed Approach

The Dagstuhl abstract model proposed treating agents as **entities with roles**: Person, Organization, and Machine are `prov:Entity` subclasses that acquire agent status through role assignment. This differs from standard PROV-DM, where Agent is a primary class alongside Entity.

The PROV_Classes.ttl implementation resolves this by modeling agents as `prov:Agent` subclasses:

```turtle
cdif:Person    a prov:Agent, rdfs:Class .
cdif:Organization  a prov:Agent, rdfs:Class .
cdif:Machine   a prov:Agent, rdfs:Class .
```

Roles (Observer, Generator/Creator, Participant, Consumer, Provider, Instrument Role, Sensor Role) are modeled as `prov:role` values on the appropriate agent or entity.

### 4.2 Concerns and Open Questions

The commentary in PROV_Classes.ttl raises several issues that remain relevant:

1. **Entity-as-Agent tension:** The abstract model's proposal to make agents "entities with roles" is "contrary to how the other vocabularies used in CDIF do it (ODRL, DDI-CDI) and also seems to break the PROV Information Model." In standard PROV, an Agent *can* also be an Entity, but its agency is intrinsic, not granted through role assignment.

2. **Instrument as entity vs. agent:** The abstract model assigns an "Instrument Role" to entities, treating instruments as agents. This conflicts with both schema.org (where `schema:instrument` is a property on an Action accepting any `Thing`) and PROV-O (where instruments are `prov:Entity` used by activities, not agents). In social science contexts, an instrument (e.g., a survey) may be "a combination of documentary resources, software, persons, and machines" — not simply a machine playing a role.

3. **Machine agency:** The `cdif:Machine` class is defined as "an artificial agent which has been manufactured to perform one or more tasks. Distinct from a tool in that it possesses agency." This distinction between machines-with-agency and tools-without-agency is meaningful but not well-supported by the other vocabularies. Schema.org has no such distinction; PROV-O has `prov:SoftwareAgent` but no hardware equivalent.

4. **Role vocabulary fragmentation:** The abstract model defines domain-specific role types (Observer, Generator, Consumer, Provider, Sensor) that overlap with but don't match schema.org's role vocabulary or DDI-CDI's ProcessingAgent typing.

## 5. Agents in WRROC and ARC Profiles

### 5.1 Standard WRROC

WRROC uses unqualified schema.org for agents:

```json
{
    "@type": "CreateAction",
    "agent": {"@id": "#person-jane"},
    ...
}
```

Agent entities are `Person` or `Organization` nodes in the RO-Crate `@graph` with standard schema.org properties (name, email, affiliation, identifier). No role qualification mechanism is defined.

### 5.2 ARC Profile

The ARC profile follows the same pattern as standard WRROC but adds `Organization` agents for institutional contributors (labs, research groups). No additional agent types or role mechanisms are introduced.

### 5.3 Mapping to cdifProv

WRROC/ARC agents map directly to cdifProv:
- `Person` → `schema:Person` as `schema:agent`
- `Organization` → `schema:Organization` as `schema:agent`
- Multiple agents → first as `schema:agent`, remainder as `schema:participant`

The [WRROCToCdifProv.py](tools/WRROCToCdifProv.py) converter handles this mapping, inlining agent details at first occurrence and using `@id` references thereafter.

### 5.4 Galaxy RO-Crate Converters

The Galaxy RO-Crate converters ([galaxyROCrateToCDIF.py](tools/galaxyROCrateToCDIF.py) and [galaxyROCrateToCDIFActions.py](tools/galaxyROCrateToCDIFActions.py)) represent computational tools as software agents using `bios:computationalTool` on the workflow's `schema:HowTo` or individual step activities. Each Galaxy tool is typed as `schema:SoftwareApplication` with name, version, and identifier (Galaxy tool shed ID). This follows the recommendation in §7.5 below — software tools that execute workflow steps are treated as instruments rather than primary agents, since the workflow engine orchestrates them.

## 6. Comparison Table

| Aspect | cdifProv | provActivity | ddicdiProv | Dagstuhl PROV | WRROC/ARC |
|---|---|---|---|---|---|
| **Agent property** | `schema:agent` | `prov:wasAssociatedWith` | `cdi:performs` (inverted) | `prov:wasAssociatedWith` | `agent` |
| **Direction** | activity → agent | activity → agent | agent → activity | activity → agent | activity → agent |
| **Person type** | `schema:Person` | `schema:Person` | — | `cdif:Person` | `Person` |
| **Organization type** | `schema:Organization` | `schema:Organization` | — | `cdif:Organization` | `Organization` |
| **Machine/Software type** | — | — | — | `cdif:Machine` | `SoftwareApplication` |
| **Role mechanism** | `schema:Role` wrapper (AgentInRole) | Not implemented (deferred) | Implicit in `ProcessingAgent` | `prov:role` values | None |
| **Multiple agents** | `schema:agent` + `schema:participant` | Multiple `prov:wasAssociatedWith` | Multiple `ProcessingAgent` nodes | Multiple `prov:wasAssociatedWith` | Multiple `agent` values |
| **Agent inline?** | Yes | Yes | No (separate node) | N/A (ontology only) | Yes (or @id ref) |

## 7. Recommendations

### 7.1 Use schema.org Types for Agent Description

Regardless of which CDIF building block is used for the activity, agent *descriptions* should use schema.org types (`schema:Person`, `schema:Organization`) with schema.org properties (name, identifier, affiliation, contactPoint). This provides:
- Consistent agent metadata across all building blocks
- Web discoverability (search engines understand schema.org Person/Organization)
- Rich description capabilities (ORCID, ROR, email, affiliation hierarchies)

PROV-O and DDI-CDI define agent types but no descriptive properties, so schema.org is the practical choice for the description regardless.

### 7.2 Use the AgentInRole Pattern for Qualified Roles

When an agent's role matters (Principal Investigator vs. Technician vs. Data Curator), use the cdifProv AgentInRole pattern (`schema:Role` wrapping the agent with `schema:roleName`). This is:
- Simpler than PROV-O's `qualifiedAssociation` mechanism
- More expressive than WRROC's unqualified `agent` property
- Compatible with schema.org's existing Role infrastructure
- Understandable by web consumers

### 7.3 Distinguish Primary and Secondary Agents

Use `schema:agent` for the primary responsible agent and `schema:participant` for other contributors. This matches natural language usage ("who did this?" → agent; "who else was involved?" → participants) and avoids the need for role qualification in simple cases.

### 7.4 Avoid the Inverted Agent Pattern

The DDI-CDI pattern (`agent --performs--> activity`) should be contained within ddicdiProv building block usage and not propagated to other CDIF contexts. The activity → agent direction used by schema.org, PROV-O, and WRROC is the dominant pattern across web and provenance standards.

### 7.5 Software Agents

For software tools and computational workflows that act as agents (not just instruments), use `schema:SoftwareApplication` as the agent type. This covers:
- Workflow engines that orchestrate multi-step processes
- Analysis software that autonomously produces results
- AI/ML systems with delegated decision-making

For physical instruments that are *used by* an activity but do not have independent agency, use `schema:instrument` (on the action or within `prov:used`) rather than treating them as agents.

### 7.6 Alignment with Dagstuhl Vocabulary

If the Dagstuhl PROV activity classes (Sampling, Observing/Measuring, Creating, DataTransforming, etc.) are adopted as `schema:additionalType` values on cdifProv activities, the associated role vocabulary should be mapped to `schema:roleName` values within the AgentInRole pattern rather than introducing a parallel `prov:role` mechanism. This keeps the agent model consistent while allowing domain-specific role vocabularies.

## 8. Sources

- [W3C PROV-DM: The PROV Data Model](https://www.w3.org/TR/prov-dm/) — Section 3: Agents and Responsibility
- [W3C PROV-O: The PROV Ontology](https://www.w3.org/TR/prov-o/) — Agent, Association, qualifiedAssociation
- [schema.org Person](https://schema.org/Person), [Organization](https://schema.org/Organization), [Role](https://schema.org/Role)
- [schema.org agent property](https://schema.org/agent) — on Action
- [DDI-CDI 1.0 Specification](https://ddialliance.org/Specification/DDI-CDI/1.0/) — ProcessingAgent
- [PROV_Classes.ttl](PROV_Classes.ttl) — Dagstuhl Workshop provenance classes (November 2025)
- [ODIS Architecture: Common Provenance Cases](https://github.com/iodepo/odis-arch/blob/414-update-provenance-recommendations/book/thematics/provenance/common-provenance-cases.md)
- [Workflow Run RO-Crate](https://www.researchobject.org/workflow-run-crate/)
- [ARC WR RO-Crate Profile](https://github.com/nfdi4plants/arc-wr-ro-crate-profile)
