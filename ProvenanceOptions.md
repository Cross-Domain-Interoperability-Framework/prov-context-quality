# CDIF Provenance Options: Building Blocks and External Profile Integration

**Date:** 2026-03-11
**Status:** Draft for review

## 1. Overview

CDIF provides multiple building blocks for describing the activities that produce datasets. All follow the W3C PROV pattern: `Dataset --prov:wasGeneratedBy--> Activity`. Each building block uses a different primary vocabulary while describing the same provenance concepts: what was done, who did it, what was used, what was produced, and how it was done.

In addition to the native CDIF building blocks, the research community has developed RO-Crate-based provenance profiles — particularly the **Workflow Run RO-Crate (WRROC)** family and the **ARC Workflow Run RO-Crate** profile — that describe computational and laboratory workflows. This document compares all approaches and discusses how WRROC and ARC provenance can be integrated into CDIF.

### CDIF Building Blocks

| Building Block | Primary Vocabulary | Activity Type | Location |
|---|---|---|---|
| **cdifProv** | schema.org + PROV-O | `["schema:Action", "prov:Activity"]` | [cdifProperties/cdifProv](https://github.com/usgin/metadataBuildingBlocks/tree/main/_sources/cdifProperties/cdifProv) |
| **provActivity** | W3C PROV-O | `["prov:Activity"]` | [provProperties/provActivity](https://github.com/usgin/metadataBuildingBlocks/tree/main/_sources/provProperties/provActivity) |
| **ddicdiProv** | DDI-CDI 1.0 | `cdi:Activity` | [ddiProperties/ddicdiProv](https://github.com/usgin/metadataBuildingBlocks/tree/main/_sources/ddiProperties/ddicdiProv) |

### External Provenance Profiles

| Profile | Vocabulary | Activity Type | Specification |
|---|---|---|---|
| **Process Run Crate** | schema.org | `schema:CreateAction` | [w3id.org/ro/wfrun/process/0.5](https://w3id.org/ro/wfrun/process/0.5) |
| **Workflow Run Crate** | schema.org | `schema:CreateAction` + `schema:OrganizeAction` | [w3id.org/ro/wfrun/workflow/0.5](https://w3id.org/ro/wfrun/workflow/0.5) |
| **Provenance Run Crate** | schema.org + CWLProv | `schema:CreateAction` + `schema:OrganizeAction` | [w3id.org/ro/wfrun/provenance/0.1](https://w3id.org/ro/wfrun/provenance/0.1) |
| **ARC WR RO-Crate** | schema.org + Bioschemas | `schema:CreateAction` + `LabProcess` | [nfdi4plants/arc-wr-ro-crate-profile](https://github.com/nfdi4plants/arc-wr-ro-crate-profile) |

### Links to Schemas and Examples

| Building Block | Resolved Schema | Example Instance |
|---|---|---|
| cdifProv | [resolvedSchema.json](https://github.com/usgin/metadataBuildingBlocks/blob/main/_sources/cdifProperties/cdifProv/resolvedSchema.json) | [exampleCdifProv.json](https://github.com/usgin/metadataBuildingBlocks/blob/main/_sources/cdifProperties/cdifProv/exampleCdifProv.json) |
| provActivity | [provActivitySchema.json](https://github.com/usgin/metadataBuildingBlocks/blob/main/_sources/provProperties/provActivity/provActivitySchema.json) | [exampleProvActivity.json](https://github.com/usgin/metadataBuildingBlocks/blob/main/_sources/provProperties/provActivity/exampleProvActivity.json) |
| ddicdiProv | [resolvedSchema.json](https://github.com/usgin/metadataBuildingBlocks/blob/main/_sources/ddiProperties/ddicdiProv/resolvedSchema.json) | [exampleDdicdiProv.json](https://github.com/usgin/metadataBuildingBlocks/blob/main/_sources/ddiProperties/ddicdiProv/exampleDdicdiProv.json) |

WRROC conversion examples (Galaxy workflow RO-Crates from [Zenodo record 13842780](https://zenodo.org/records/13842780) and Bennu py-GC-MS analytical workflow) are available in the [prov-context-quality/Examples](./Examples/) folder.

## 2. CDIF Building Block Design

### cdifProv — Schema.org-first with PROV-O linkage

The cdifProv building block is the primary CDIF recommendation. It follows the approach developed by the [ODIS Architecture](https://github.com/iodepo/odis-arch/blob/414-update-provenance-recommendations/book/thematics/provenance/common-provenance-cases.md) provenance recommendations, mapping schema.org `Action` to `prov:Activity` and using schema.org properties to describe provenance in a vocabulary already familiar to web developers and search engines.

Activity nodes carry dual types `["schema:Action", "prov:Activity"]` so that:
- Schema.org-aware consumers (search engines, web crawlers) see a well-typed `Action`
- PROV-aware consumers (provenance trackers, RDF reasoners) see a `prov:Activity`
- The `prov:used` property provides backward-compatible input listing

Key properties: `schema:agent`, `schema:object` (inputs), `schema:result` (outputs), `schema:instrument`, `schema:actionProcess` → `schema:HowTo` (methodology), `schema:startTime`, `schema:endTime`, `schema:location`, `schema:actionStatus`.

### provActivity — PROV-O-first with schema.org fallbacks

Prioritizes W3C PROV-O vocabulary, using native PROV-O properties where they exist (`prov:wasAssociatedWith`, `prov:generated`, `prov:startedAtTime`, `prov:wasInformedBy`) and falling back to schema.org for concepts PROV-O does not cover (name, description, instrument, methodology, status). Appropriate for communities invested in PROV-O tooling or where formal provenance reasoning is needed.

### ddicdiProv — DDI-CDI native workflow description

Uses the [DDI-CDI 1.0](https://ddialliance.org/Specification/DDI-CDI/1.0/) vocabulary natively. Designed for communities using DDI-CDI for statistical and survey data, with detailed workflow modeling capabilities (Steps, Parameters, data flow between steps, ProcessingAgents, ProductionEnvironments). Based on the [BBeuster EU-SoGreen-Prov](https://github.com/ddialliance/ddi-cdi_provenance-examples) example pattern.

## 3. Workflow Run RO-Crate (WRROC) Profiles

The [Workflow Run RO-Crate](https://www.researchobject.org/workflow-run-crate/) specification defines three profile levels for capturing retrospective provenance of computational and analytical workflows. All build on the [RO-Crate 1.1](https://w3id.org/ro/crate/1.1) packaging standard and use schema.org as the primary vocabulary.

### 3.1 Profile Hierarchy

**Process Run Crate** (`https://w3id.org/ro/wfrun/process/0.5`)
The minimal level. Captures a single tool execution as a `schema:CreateAction` with:
- `object`: input files (File/MediaObject)
- `result`: output files
- `instrument`: the SoftwareApplication that was run
- `agent`: the Person who ran it
- `actionStatus`: CompletedActionStatus, FailedActionStatus, etc.
- `startTime`, `endTime`: execution timestamps
- `error`: error message if the action failed

**Workflow Run Crate** (`https://w3id.org/ro/wfrun/workflow/0.5`)
Extends Process Run Crate for multi-step workflows. Adds:
- `schema:OrganizeAction`: a top-level action orchestrating sub-actions (linked from `instrument` pointing to a `ComputationalWorkflow`)
- `schema:CreateAction` per workflow step (linked via `instrument` pointing to a `HowToStep`)
- `ComputationalWorkflow` entity with `input`/`output` arrays of `FormalParameter`, `programmingLanguage`, `hasPart` (sub-steps)
- `FormalParameter` entities describing expected inputs/outputs with types, format constraints, default values

**Provenance Run Crate** (`https://w3id.org/ro/wfrun/provenance/0.1`)
Extends Workflow Run Crate with CWLProv-style detailed provenance:
- `schema:ControlAction` for workflow engine orchestration
- Per-step resource usage, container images, environment details
- Connections between step inputs/outputs via `exampleOfWork` references to FormalParameters

### 3.2 WRROC's Relationship to CDIF

WRROC is designed for **retrospective provenance** — describing what actually happened when a workflow was executed. This aligns directly with CDIF's purpose: documenting how a dataset was generated. However, WRROC also captures **prospective provenance** (workflow definitions, FormalParameters) which serves as valuable context.

Key alignment points:
- Both use schema.org as the primary vocabulary
- Both describe activities with inputs, outputs, agents, and instruments
- Both support multi-step activity chains
- Both capture temporal bounds and completion status

Key differences:
- WRROC uses `schema:CreateAction` (no PROV-O dual typing); cdifProv uses `["schema:Action", "prov:Activity"]`
- WRROC uses `schema:object`/`schema:result` for action I/O; cdifProv uses `prov:used` for inputs (inherited from the `generatedBy` base building block) alongside `schema:result` for outputs
- WRROC uses `schema:instrument` at the action level for the tool/workflow; cdifProv nests instruments within `prov:used` items
- WRROC defines methodology implicitly through the workflow structure; cdifProv uses explicit `schema:actionProcess` → `schema:HowTo` for methodology

## 4. ARC Workflow Run RO-Crate Profile

The [ARC (Annotated Research Context) Workflow Run RO-Crate profile](https://github.com/nfdi4plants/arc-wr-ro-crate-profile) extends WRROC for laboratory analytical workflows. Developed by [DataPLANT/nfdi4plants](https://nfdi4plants.org/), it adds [Bioschemas](https://bioschemas.org/) types to capture the structured, parameterized nature of lab processes.

### 4.1 Key Additions Over Standard WRROC

| Concept | Standard WRROC | ARC Profile |
|---|---|---|
| Activity type | `CreateAction` | `CreateAction` + `LabProcess` |
| Methodology | `ComputationalWorkflow` | `ComputationalWorkflow` + `LabProtocol` |
| Process parameters | Not captured | `parameterValue` → `PropertyValue` array |
| Lab equipment | `instrument` (generic) | `labEquipment` on LabProtocol |
| Samples | `File`/`MediaObject` | `Sample` (Bioschemas type) |
| Protocol execution | `instrument` → workflow | `executesLabProtocol` → `LabProtocol` |
| Instrument detail | `SoftwareApplication` | `DefinedTerm` (physical instruments) |

### 4.2 ARC Entity Types

**LabProcess** (extends `CreateAction`)
A lab process execution. Carries `executesLabProtocol` pointing to the protocol followed, and `parameterValue` arrays with the actual measurement parameters used (temperature, pressure, flow rate, etc.).

**LabProtocol** (extends `CreativeWork`)
Describes how a lab process should be carried out. Contains:
- `labEquipment`: instruments and equipment used (DefinedTerm references)
- `intendedUse`: purpose description
- `measurementMethod`: analytical method
- `input`/`output`: expected parameters (FormalParameter references)

**Sample** (Bioschemas type)
Represents physical samples with `additionalProperty` for sample-specific metadata (mass, preparation method, container type).

**DefinedTerm** (for instruments)
Physical lab equipment described with name, description, identifier, and URL. Unlike `SoftwareApplication` used for computational tools, `DefinedTerm` captures instruments that don't have software versions.

**PropertyValue** (via `parameterValue`)
Actual parameter values used during execution: temperature (600°C), ramp rate (10°C/ms), scan range (m/z 50–500), column dimensions, etc. Each PropertyValue has `value`, `unitText`, and optionally `propertyID` linking to a controlled vocabulary term.

### 4.3 Bennu py-GC-MS Example

The [Bennu-py-GC-MSarc](./Examples/Bennu-py-GC-MSarc-ro-crate-metadata.json) example demonstrates the ARC profile for a multi-step analytical workflow: pyrolysis-GC-MS/MS analysis of asteroid sample OREX-803003-0 from the OSIRIS-REx mission. The workflow chains five activities:

1. **Sample Preparation** → quartz tube loading, mass measurement
2. **Flash Pyrolysis** → 600°C at 10°C/ms ramp rate, He carrier gas
3. **GC Separation** → Rtx-5ms column, temperature program 35°C→310°C
4. **MS Detection (Full Scan)** → m/z 50–500, EI positive mode
5. **MS Detection (MRM/SRM)** → 38 targeted compounds, timed transitions

Each step carries rich `parameterValue` arrays with actual instrument settings. Equipment (`DefinedTerm` entities: pyrolysis oven, gas chromatograph, TSQ triple-quad mass spectrometer) is declared on the protocol and referenced by steps.

The [converted cdifProv output](./Examples/Bennu-py-GC-MSarc.cdifprov.json) demonstrates how all ARC concepts map cleanly to cdifProv vocabulary.

## 5. Mapping WRROC/ARC to cdifProv

A converter tool ([WRROCToCdifProv.py](https://github.com/Cross-Domain-Interoperability-Framework/packaging/tree/main/tools/WRROCToCdifProv.py)) has been developed to transform WRROC and ARC RO-Crate files into cdifProv-compatible `@graph` documents.

### 5.1 Property Mapping

| WRROC / ARC | cdifProv | Notes |
|---|---|---|
| `@type: CreateAction` | `@type: ["schema:Action", "prov:Activity"]` | Original type preserved in `schema:additionalType` |
| `@type: LabProcess` | `schema:additionalType: ["schema:LabProcess"]` | ARC-specific action subtype |
| `@type: OrganizeAction` | `schema:additionalType: ["schema:OrganizeAction"]` | Orchestration actions |
| `object` (inputs) | `prov:used` | cdifProv inherits `prov:used` from base |
| `result` (outputs) | `schema:result` | Direct mapping |
| `instrument` (tool) | `schema:instrument` on `prov:used` items, or `schema:actionProcess` | Depends on type — workflows become actionProcess |
| `agent` | `schema:agent` | Direct mapping (Person, Organization) |
| `startTime` / `endTime` | `schema:startTime` / `schema:endTime` | Direct mapping |
| `actionStatus` | `schema:actionStatus` | Normalized to prefixed form |
| `error` | `schema:error` | Direct mapping |
| `executesLabProtocol` | `schema:actionProcess` | Protocol → HowTo methodology |
| `parameterValue` | `schema:additionalProperty` | PropertyValue objects preserved |
| `labEquipment` | `schema:instrument` (on actionProcess node) | Equipment on protocol, not action |
| `ComputationalWorkflow` | `schema:SoftwareApplication` | With additionalType preserving original |
| `LabProtocol` | `schema:HowTo` | Methodology description |
| `FormalParameter` | `schema:MediaObject` | With `additionalType: ["schema:FormalParameter"]` |
| `Sample` | `schema:Thing` | With `additionalType: ["bioschemas:Sample"]` |
| `DefinedTerm` (instrument) | `["schema:Thing", "schema:DefinedTerm"]` | Physical instrument description |

### 5.2 Structural Transformation

The converter produces a `@graph` array where each execution action (CreateAction, OrganizeAction, LabProcess) becomes a top-level node. All referenced entities — instruments, files, parameters, samples, agents — are inlined at their first occurrence within an activity node. Subsequent references use `{"@id": "..."}` only.

```
RO-Crate flat @graph:          cdifProv nested @graph:
  CreateAction₁                  Activity₁
  CreateAction₂                    +-- prov:used [inline entities]
  OrganizeAction                   +-- schema:result [inline entities]
  ComputationalWorkflow            +-- schema:actionProcess [inline workflow]
  FormalParameter₁                 +-- schema:agent [inline person]
  FormalParameter₂                 +-- schema:additionalProperty [params]
  SoftwareApplication            Activity₂
  Person                           +-- prov:used [inline or @id refs]
  File₁ ... FileN                  +-- ...
```

### 5.3 What Maps Cleanly

- **Activities**: CreateAction, OrganizeAction, and LabProcess all map naturally to cdifProv's dual-typed `["schema:Action", "prov:Activity"]` pattern. The original action subtype is preserved in `schema:additionalType`.
- **Temporal bounds**: `startTime`/`endTime` are direct mappings.
- **Agents**: Person and Organization inline directly as `schema:agent`.
- **Action status**: Maps directly with URI normalization.
- **Parameter values**: ARC's `parameterValue` PropertyValue arrays map cleanly to `schema:additionalProperty`, preserving value, unitText, and propertyID.
- **Lab protocols**: `executesLabProtocol` → `schema:actionProcess` is a natural fit, as both describe the methodology an activity follows.
- **Lab equipment**: `labEquipment` on protocols maps to `schema:instrument` on the methodology node.
- **Samples**: Bioschemas `Sample` maps to `schema:Thing` with `schema:additionalType`.

### 5.4 What Requires Interpretation

- **FormalParameter → MediaObject**: WRROC's `FormalParameter` (which describes expected I/O slots) has no direct schema.org equivalent. Since `schema:object`/`prov:used` and `schema:result` expect `schema:CreativeWork` or similar, and most FormalParameters describe file-like entities, `schema:MediaObject` with `additionalType: ["schema:FormalParameter"]` is used.
- **Nested instrument placement**: WRROC places `instrument` directly on the action; cdifProv nests instruments within `prov:used` items. The converter places instruments either on the `schema:actionProcess` (workflow/protocol) node or as `schema:instrument` on the activity, depending on context.
- **Workflow as methodology vs. instrument**: In WRROC, the `ComputationalWorkflow` is the `instrument` of an `OrganizeAction`. In cdifProv, it's more natural to treat it as `schema:actionProcess` (methodology). The converter maps it to `schema:actionProcess` for actions that `executesLabProtocol`, and as `schema:instrument` context otherwise.
- **Bioschemas vocabulary**: Terms like `LabProcess`, `LabProtocol`, `Sample` are Bioschemas extensions not in the core schema.org vocabulary. These are preserved as `additionalType` values with a `bioschemas:` prefix where appropriate.

### 5.5 Conversion Examples

Six Galaxy workflow RO-Crates from [Zenodo record 13842780](https://zenodo.org/records/13842780) have been converted, demonstrating computational workflow provenance (FeS2 analysis, Pt3Sn catalyst, Au colloids, LaMnO3 catalytic behaviour, EXAFS fitting, Diphosphine workflow). The Bennu py-GC-MS example demonstrates both standard WRROC and ARC profile conversion for laboratory analytical workflows.

All examples are in the [Examples](./Examples/) folder with `.rocrate.json` (source) and `.cdifprov.json` (converted) pairs.

## 6. Representing Multi-Step Provenance

When a dataset is produced by a multi-step process (analytical workflow, computational pipeline), there are two structural options within cdifProv for representing the steps.

### Option A: Activity list in `prov:wasGeneratedBy`

Each step is a separate `["schema:Action", "prov:Activity"]` node in the `@graph` array. The dataset's `prov:wasGeneratedBy` points to all of them (or to the final activity, which chains backward via `schema:object` referencing prior activities' `schema:result`).

```json
{
  "@type": "schema:Dataset",
  "prov:wasGeneratedBy": [
    { "@id": "#step1" },
    { "@id": "#step2" },
    { "@id": "#step3" }
  ]
}
```

**Advantages:**
- Each step is a full `prov:Activity`, enabling independent provenance queries
- Activity chaining via `schema:object`/`schema:result` captures data flow between steps
- Maps directly to WRROC's flat action model — each CreateAction becomes a graph node
- Allows different agents, instruments, and temporal bounds per step
- Supports partial provenance: consumers can process individual steps without understanding the whole chain

**Disadvantages:**
- No explicit ordering unless chained through `schema:object`/`schema:result` references
- The overall workflow structure (which steps belong to which workflow) is less visible
- Multiple activity nodes increase document complexity

### Option B: Steps as `schema:step` in `schema:actionProcess`

A single `["schema:Action", "prov:Activity"]` represents the overall process. The detailed steps are `schema:HowToStep` entries within a `schema:HowTo` linked via `schema:actionProcess`.

```json
{
  "@type": ["schema:Action", "prov:Activity"],
  "schema:actionProcess": {
    "@type": "schema:HowTo",
    "schema:name": "Py-GC-MS/MS analysis protocol",
    "schema:step": [
      {
        "@type": "schema:HowToStep",
        "schema:name": "Sample preparation",
        "schema:position": 1,
        "schema:text": "Load 0.5mg sample into quartz tube..."
      },
      {
        "@type": "schema:HowToStep",
        "schema:name": "Flash pyrolysis",
        "schema:position": 2,
        "schema:text": "Heat at 600°C, 10°C/ms ramp rate..."
      }
    ]
  }
}
```

**Advantages:**
- Compact: single activity node with embedded methodology
- Explicit ordering via `schema:position`
- Clear that steps belong to a single process
- Human-readable: steps read like a protocol
- Search engines understand `schema:HowTo` / `schema:HowToStep`

**Disadvantages:**
- `HowToStep` is not a `prov:Activity` — step-level provenance queries are not possible
- Cannot capture per-step agents, instruments, temporal bounds, or parameter values
- Steps are prospective (how it *should* be done) rather than retrospective (what *was* done)
- Less information: actual parameter values, error states, and execution metadata cannot be attached to individual steps

### Recommendation

Both approaches are valid cdifProv. The choice depends on the level of detail:

- **Use Option A** (activity list) when each step has its own instruments, parameters, agents, temporal bounds, or when step-level provenance queries matter. This is the natural mapping for WRROC and ARC conversions where each action carries rich execution metadata.
- **Use Option B** (HowTo steps) when the methodology is the primary concern and step-level execution detail is not needed — e.g., describing a standard operating procedure without per-step timestamps or parameter values.
- **Combine both**: Use Option A for the retrospective provenance (what was done) and include `schema:actionProcess` on each activity pointing to the protocol/methodology (how it should be done). This is what the ARC profile naturally produces — `LabProcess` activities with `executesLabProtocol` → `LabProtocol`.

## 7. Property Mapping Across All Approaches

| Concept | cdifProv | provActivity | ddicdiProv | WRROC | ARC Profile |
|---|---|---|---|---|---|
| **Activity type** | `["schema:Action", "prov:Activity"]` | `["prov:Activity"]` | `cdi:Activity` | `CreateAction` | `CreateAction` + `LabProcess` |
| **Name** | `schema:name` | `schema:name` | `cdi:name` | `name` | `name` |
| **Description** | `schema:description` | `schema:description` | `cdi:description` | `description` | `description` |
| **Inputs** | `prov:used` | `prov:used` | `cdi:entityUsed` | `object` | `object` |
| **Outputs** | `schema:result` | `prov:generated` | `cdi:entityProduced` | `result` | `result` |
| **Agent** | `schema:agent` | `prov:wasAssociatedWith` | `cdi:ProcessingAgent` | `agent` | `agent` |
| **Instrument** | `schema:instrument` (in `prov:used`) | `schema:instrument` (in `prov:used`) | `cdi:entityUsed` | `instrument` | `labEquipment` (on protocol) |
| **Methodology** | `schema:actionProcess` → `HowTo` | `schema:actionProcess` → `HowTo` | `cdi:has_Step` | `ComputationalWorkflow` | `executesLabProtocol` → `LabProtocol` |
| **Start time** | `schema:startTime` | `prov:startedAtTime` | — | `startTime` | `startTime` |
| **End time** | `schema:endTime` | `prov:endedAtTime` | — | `endTime` | `endTime` |
| **Parameters** | `schema:additionalProperty` | — | `cdi:Parameter` | — | `parameterValue` |
| **Status** | `schema:actionStatus` | `schema:actionStatus` | — | `actionStatus` | `actionStatus` |
| **Error** | `schema:error` | `schema:error` | — | `error` | `error` |
| **Activity chain** | `schema:object`/`result` | `prov:wasInformedBy` | `cdi:receives`/`produces` | `object`/`result` | `object`/`result` |
| **Samples** | `schema:Thing` | `prov:Entity` | `cdi:entityUsed` | `File` | `Sample` |

## 8. Benefits and Challenges

### cdifProv

**Benefits:**
- Broadest interoperability with web infrastructure: schema.org Action is understood by Google Dataset Search, web crawlers, and general-purpose JSON-LD consumers
- Aligned with [ODIS/OIH provenance recommendations](https://github.com/iodepo/odis-arch/blob/414-update-provenance-recommendations/book/thematics/provenance/common-provenance-cases.md)
- Dual typing bridges schema.org and PROV-O worlds
- Compact single-node or multi-node serialization
- `schema:actionProcess` → `HowTo` → `HowToStep` provides human-readable methodology
- Cleanly accommodates WRROC and ARC profile content through conversion

**Challenges:**
- `schema:actionProcess` is present on the schema.org website (V29.4+) but not yet in downloadable RDF vocabulary files
- Dual typing adds a concept (`schema:Action`) less familiar to provenance specialists

### provActivity

**Benefits:**
- Canonical W3C PROV-O property names enable direct use with PROV-O reasoning tools
- Supports PROV-O expanded terms (`prov:wasStartedBy`, `prov:wasEndedBy`, `prov:atLocation`)
- Activity-to-activity chaining via `prov:wasInformedBy` is more precise than schema.org's `object`/`result` pattern

**Challenges:**
- PROV-O property names not recognized by search engines
- Mixed `prov:` and `schema:` prefixes may confuse implementers
- No native methodology property in PROV-O outside of qualified associations

### ddicdiProv

**Benefits:**
- Native DDI-CDI vocabulary compatible with DDI-CDI statistical infrastructure
- Explicit data-flow modeling via `cdi:Parameter` with `cdi:receives` / `cdi:produces`
- `cdi:Step` nodes with `cdi:script` for executable code references
- `cdi:standardModelMapping` links to standard process models (e.g., GSBPM)

**Challenges:**
- DDI-CDI vocabulary specialized and not widely recognized outside statistical community
- Multi-node graph structure ~2.5× more verbose for the same scenario
- Cannot express temporal bounds, status, or location directly on Activity
- No dedicated instrument class
- Not understood by web search engines

### WRROC / ARC

**Benefits:**
- Established community adoption in computational and life science workflows
- Rich retrospective provenance capturing actual execution details
- ARC profile adds structured parameterization well-suited for analytical chemistry
- RO-Crate packaging bundles provenance with the data files it describes
- Conversion to cdifProv is straightforward and largely lossless

**Challenges:**
- Uses unqualified schema.org property names (no namespace prefixes) — requires JSON-LD context processing
- `schema:input`/`schema:output` (Bioschemas properties used in some implementations) are not in core schema.org; the standard properties are `schema:object`/`schema:result`
- `FormalParameter` has no direct schema.org equivalent type
- Bioschemas types (LabProcess, LabProtocol, Sample) are community extensions, not core schema.org
- RO-Crate's flat `@graph` structure requires restructuring for cdifProv's nested inline pattern

## 9. Implementing ARC Profile Support in CDIF

The ARC Workflow Run RO-Crate profile is particularly relevant for CDIF because it addresses the same domain: describing how scientific datasets were produced through analytical processes with specific instruments and parameters.

### 9.1 Natural Mappings

The ARC profile's core concepts map directly to cdifProv:

| ARC Concept | cdifProv Implementation |
|---|---|
| `LabProcess` execution | Activity node with `additionalType: ["schema:LabProcess"]` |
| `executesLabProtocol` | `schema:actionProcess` → `schema:HowTo` node |
| `parameterValue` array | `schema:additionalProperty` → `PropertyValue` objects |
| `labEquipment` | `schema:instrument` on the methodology (actionProcess) node |
| `Sample` | `schema:Thing` with `additionalType: ["bioschemas:Sample"]` in `prov:used` |
| `DefinedTerm` instruments | `["schema:Thing", "schema:DefinedTerm"]` with identifier, description |
| Activity chaining (output → input) | `schema:result` on Activity₁ referenced in `prov:used` on Activity₂ |

### 9.2 What the Bennu Example Demonstrates

The Bennu py-GC-MS/MS analysis ([standard](./Examples/Bennu-py-GC-MS.cdifprov.json) and [ARC](./Examples/Bennu-py-GC-MSarc.cdifprov.json) versions) demonstrates:

1. **Multi-step analytical chain**: Five activities linked through their inputs and outputs, capturing the complete analytical pathway from sample preparation through mass spectrometric detection.

2. **Rich parameterization**: Each step carries actual instrument settings as `schema:additionalProperty` PropertyValue objects — pyrolysis temperature (600°C), GC column dimensions (30m × 0.250mm × 0.50µm), MS scan range (m/z 50–500), number of targeted MRM compounds (38). These are preserved losslessly in the cdifProv output.

3. **Protocol-equipment binding**: Instruments (pyrolysis oven, gas chromatograph, TSQ triple-quad mass spectrometer) are declared on the protocol (`schema:actionProcess`) and referenced by the steps that use them. This cleanly separates "what equipment exists" from "which step used it."

4. **Sample tracking**: Bioschemas `Sample` entities track the physical sample through the workflow, with sample-specific metadata (mass, preparation method) carried as `additionalProperty`.

### 9.3 Recommendations for CDIF Adopters

1. **Use `WRROCToCdifProv.py` for automated conversion** from existing WRROC/ARC RO-Crate files to cdifProv. The converter handles both standard WRROC (computational workflows) and ARC profile (lab analytical workflows).

2. **For new analytical provenance**, author directly in cdifProv using ARC-inspired patterns:
   - Use `schema:additionalProperty` with PropertyValue objects for instrument parameters
   - Use `schema:actionProcess` → `schema:HowTo` for protocol/methodology
   - Use `schema:DefinedTerm` for physical instruments (as opposed to `schema:SoftwareApplication` for software tools)
   - Chain activities through `schema:object`/`prov:used` → `schema:result` references

3. **Preserve domain-specific types** via `schema:additionalType`. When converting from ARC, keep `LabProcess`, `LabProtocol`, `Sample` as additionalType values so domain-specific consumers can identify them.

## 10. When to Use Each Approach

| Use Case | Recommended Approach |
|---|---|
| General CDIF metadata with web discoverability | **cdifProv** |
| Interoperability with ODIS / Ocean InfoHub | **cdifProv** |
| Converting existing WRROC/ARC workflow provenance | **cdifProv** (via converter) |
| PROV-O tooling and formal provenance reasoning | **provActivity** |
| DDI-CDI infrastructure and statistical workflows | **ddicdiProv** |
| Detailed data-flow modeling between processing steps | **ddicdiProv** |
| Lab analytical workflows with rich parameterization | **cdifProv** with ARC-inspired patterns |
| Minimal authoring effort | **cdifProv** or **provActivity** |

Multiple building blocks can coexist. A Dataset's `prov:wasGeneratedBy` can point to an activity described using any approach, and the base `generatedBy` building block provides a minimal common denominator that all PROV-aware consumers can process.

## 11. Shared Infrastructure

### Base generatedBy building block

Both cdifProv and provActivity extend the [generatedBy](https://github.com/usgin/metadataBuildingBlocks/tree/main/_sources/provProperties/generatedBy) building block via JSON Schema `allOf`. The base requires `@type` containing `prov:Activity` and a `prov:used` array, ensuring any consumer that understands these can extract basic provenance from any CDIF document.

### Instrument building block

The generic [instrument](https://github.com/usgin/metadataBuildingBlocks/tree/main/_sources/schemaorgProperties/instrument) building block provides a reusable `schema:Thing`-based instrument description with `schema:hasPart` for hierarchical instrument systems.

### SHACL validation

All three building blocks include companion `rules.shacl` files providing SHACL validation shapes at three severity levels: Violation (required), Warning (recommended), Info (optional).

## 12. Sources and References

### Standards and specifications

- [W3C PROV-O: The PROV Ontology](https://www.w3.org/TR/prov-o/)
- [W3C PROV-DM: The PROV Data Model](https://www.w3.org/TR/prov-dm/)
- [DDI-CDI 1.0 Specification](https://ddialliance.org/Specification/DDI-CDI/1.0/)
- [schema.org Action](https://schema.org/Action)
- [schema.org actionProcess](https://schema.org/actionProcess) (V29.4+)
- [schema.org HowTo](https://schema.org/HowTo) / [HowToStep](https://schema.org/HowToStep)
- [schema.org instrument](https://schema.org/instrument)
- [RO-Crate 1.1 Specification](https://w3id.org/ro/crate/1.1)

### Workflow Run RO-Crate profiles

- [Process Run Crate 0.5](https://w3id.org/ro/wfrun/process/0.5)
- [Workflow Run Crate 0.5](https://w3id.org/ro/wfrun/workflow/0.5)
- [Provenance Run Crate 0.1](https://w3id.org/ro/wfrun/provenance/0.1)
- [ARC Workflow Run RO-Crate Profile](https://github.com/nfdi4plants/arc-wr-ro-crate-profile)
- [Bioschemas LabProcess](https://bioschemas.org/profiles/LabProcess)
- [Bioschemas LabProtocol](https://bioschemas.org/profiles/LabProtocol)
- [Galaxy RO-Crate workflow examples (Zenodo 13842780)](https://zenodo.org/records/13842780)

### Community recommendations and patterns

- [ODIS Architecture: Common Provenance Cases](https://github.com/iodepo/odis-arch/blob/414-update-provenance-recommendations/book/thematics/provenance/common-provenance-cases.md)
- [Ocean InfoHub (OIH)](https://oceaninfohub.org/)
- [BBeuster EU-SoGreen-Prov DDI-CDI Provenance Examples](https://github.com/ddialliance/ddi-cdi_provenance-examples)
- [UNECE Generic Statistical Business Process Model (GSBPM) v5.1](https://statswiki.unece.org/display/GSBPM/)

### Schema infrastructure

- [JSON Schema Draft 2020-12](https://json-schema.org/draft/2020-12/schema)
- [OGC Building Blocks](https://opengeospatial.github.io/bblocks/)
- [NERC Vocabulary Server (NVS)](https://vocab.nerc.ac.uk/)

### Tools

- [WRROCToCdifProv.py](https://github.com/Cross-Domain-Interoperability-Framework/packaging/tree/main/tools/WRROCToCdifProv.py) — WRROC/ARC to cdifProv converter
- [ROCrateToCDIF.py](https://github.com/Cross-Domain-Interoperability-Framework/packaging/tree/main/tools/ROCrateToCDIF.py) — RO-Crate to full CDIF metadata converter
