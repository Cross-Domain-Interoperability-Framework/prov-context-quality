#!/usr/bin/env python3
"""
Workflow Run RO-Crate to CDIF Provenance Converter

Extracts provenance information from Workflow Run RO-Crate (WRROC) files
and converts it into a CDIF-compatible @graph of nested activity nodes
using cdifProv vocabulary.

Output structure:
  - @graph contains one node per activity (CreateAction, OrganizeAction, etc.)
  - Referenced entities (instruments, files, parameters, languages) are
    inlined at their first occurrence within an activity node
  - Subsequent references use {"@id": "..."} only

Supports:
  - Process Run Crate, Workflow Run Crate, Provenance Run Crate
  - ARC Workflow Run RO-Crate profile (LabProcess, LabProtocol,
    parameterValue, labEquipment, Sample, executesLabProtocol)

Usage:
    python WRROCToCdifProv.py input-rocrate.json -o output-prov.json
    python WRROCToCdifProv.py input-rocrate.json -o output.json -v
    python WRROCToCdifProv.py input-rocrate.json  # prints to stdout

References:
    - Process Run Crate: https://w3id.org/ro/wfrun/process/0.5
    - Workflow Run Crate: https://w3id.org/ro/wfrun/workflow/0.5
    - Provenance Run Crate: https://w3id.org/ro/wfrun/provenance/0.1
    - ARC WR RO-Crate: https://github.com/nfdi4plants/arc-wr-ro-crate-profile
    - CDIF cdifProv: https://github.com/usgin/metadataBuildingBlocks/tree/main/_sources/cdifProperties/cdifProv
"""

import json
import argparse
import sys
from pathlib import Path


# CDIF output context
CDIF_PROV_CONTEXT = {
    "schema": "http://schema.org/",
    "prov": "http://www.w3.org/ns/prov#",
    "bios": "https://bioschemas.org/",
}

# Bioschemas types and properties — get bios: prefix in output
BIOSCHEMAS_TYPES = {
    "Sample", "LabProtocol", "LabProcess", "FormalParameter",
    "ComputationalWorkflow",
}
BIOSCHEMAS_PROPERTIES = {
    "computationalTool", "labEquipment", "reagent",
    "executesLabProtocol", "parameterValue",
}

# Entity types that represent execution actions (become top-level @graph nodes)
ACTION_TYPES = {
    "CreateAction", "ActivateAction", "UpdateAction", "OrganizeAction",
    "LabProcess",  # ARC profile: lab process execution
}

# RO-Crate infrastructure entities to skip entirely
SKIP_IDS = {"ro-crate-metadata.json", "ro-crate-metadata.jsonld", "./"}
PROFILE_PREFIXES = ("https://w3id.org/ro/", "https://w3id.org/workflowhub/")
GALAXY_ATTRS_SUFFIXES = ("_attrs.txt",)


def _build_entity_index(graph):
    """Build a dict mapping @id -> entity from @graph array."""
    return {e["@id"]: e for e in graph if "@id" in e}


def _get_types(entity):
    """Get @type as a set of strings."""
    t = entity.get("@type", [])
    if isinstance(t, str):
        t = [t]
    return set(t)


def _ensure_list(val):
    """Wrap scalar/dict in a list; return [] for None."""
    if val is None:
        return []
    if isinstance(val, list):
        return val
    return [val]


def _get_prop(entity, *names):
    """Get the first non-None property from an entity, trying multiple names."""
    for name in names:
        val = entity.get(name)
        if val is not None:
            return val
    return None


def _should_skip(eid):
    """Return True if this @id is RO-Crate infrastructure we never inline."""
    if eid in SKIP_IDS:
        return True
    if any(eid.startswith(p) for p in PROFILE_PREFIXES):
        return True
    if any(eid.endswith(s) for s in GALAXY_ATTRS_SUFFIXES):
        return True
    if eid.endswith(".provenance"):
        return True
    return False


def _inline_entity(entity, index, inlined):
    """Recursively inline an entity, resolving its references.

    If the entity's @id has already been inlined, returns {"@id": eid}.
    Otherwise, builds a full inline node and marks it as inlined.
    """
    if not isinstance(entity, dict):
        return entity

    eid = entity.get("@id")

    # If already inlined elsewhere, just reference
    if eid and eid in inlined:
        return {"@id": eid}

    # Mark as inlined before recursing (prevents circular refs)
    if eid:
        inlined.add(eid)

    types = _get_types(entity)

    # Dispatch to type-specific mappers (order matters)
    if types.intersection(ACTION_TYPES):
        return _build_activity_node(entity, index, inlined)

    if "LabProtocol" in types:
        return _inline_lab_protocol(entity, index, inlined)

    if "ComputationalWorkflow" in types:
        return _inline_workflow(entity, index, inlined)

    if "SoftwareApplication" in types:
        return _inline_software(entity, index, inlined)

    if "FormalParameter" in types:
        return _inline_parameter(entity, index, inlined)

    if "ComputerLanguage" in types:
        return _inline_language(entity, index, inlined)

    if "Sample" in types:
        return _inline_sample(entity, index, inlined)

    if "DefinedTerm" in types:
        return _inline_defined_term(entity, index, inlined)

    if "Organization" in types:
        return _inline_agent(entity, index, inlined)

    if "Person" in types:
        return _inline_agent(entity, index, inlined)

    if "Project" in types:
        return _inline_generic(entity, "schema:Project")

    if types.intersection({"File", "MediaObject"}):
        return _inline_file(entity, index, inlined)

    if "CreativeWork" in types:
        return _inline_creative_work(entity, index, inlined)

    # Generic fallback: include @id, name, description
    return _inline_generic_from_entity(entity)


def _resolve_and_inline(ref, index, inlined):
    """Resolve an @id reference and inline it."""
    if isinstance(ref, dict) and "@id" in ref:
        eid = ref["@id"]
        if _should_skip(eid):
            return None
        entity = index.get(eid)
        if entity:
            return _inline_entity(entity, index, inlined)
        return ref
    if isinstance(ref, str):
        if _should_skip(ref):
            return None
        entity = index.get(ref)
        if entity:
            return _inline_entity(entity, index, inlined)
        return ref
    return ref


def _inline_generic_from_entity(entity):
    """Generic fallback: include @id, name, description."""
    node = {}
    if entity.get("@id"):
        node["@id"] = entity["@id"]
    name = _get_prop(entity, "name", "schema:name")
    if name:
        node["schema:name"] = name
    desc = _get_prop(entity, "description", "schema:description")
    if desc:
        node["schema:description"] = desc
    return node


def _inline_generic(entity, schema_type):
    """Map an entity to a simple typed node."""
    node = {"@type": [schema_type]}
    if entity.get("@id"):
        node["@id"] = entity["@id"]
    name = _get_prop(entity, "name", "schema:name")
    if name:
        node["schema:name"] = name
    desc = _get_prop(entity, "description", "schema:description")
    if desc:
        node["schema:description"] = desc
    url = _get_prop(entity, "url", "schema:url")
    if url:
        node["schema:url"] = url["@id"] if isinstance(url, dict) and "@id" in url else url
    return node


# --- Type-specific inliners ---

def _inline_workflow(entity, index, inlined):
    """Inline a ComputationalWorkflow as an instrument node."""
    node = {
        "@type": ["schema:Thing", "schema:SoftwareApplication"],
    }

    if entity.get("@id"):
        node["@id"] = entity["@id"]

    name = _get_prop(entity, "name", "schema:name")
    if name:
        node["schema:name"] = name

    desc = _get_prop(entity, "description", "schema:description")
    if desc:
        node["schema:description"] = desc

    # Preserve LabProtocol additional type if present
    types = _get_types(entity)
    add_types = []
    if "LabProtocol" in types:
        add_types.append("bios:LabProtocol")
    if "ComputationalWorkflow" in types:
        add_types.append("bios:ComputationalWorkflow")
    if add_types:
        node["schema:additionalType"] = add_types

    # Programming language — inline
    prog_lang = entity.get("programmingLanguage")
    if isinstance(prog_lang, dict) and "@id" in prog_lang:
        lang = _resolve_and_inline(prog_lang, index, inlined)
        if lang:
            node["schema:programmingLanguage"] = lang
    elif prog_lang:
        node["schema:programmingLanguage"] = prog_lang

    # labEquipment (ARC profile) — inline as bios:labEquipment instruments
    lab_equip = _ensure_list(entity.get("labEquipment"))
    if lab_equip:
        equip_items = []
        for eq_ref in lab_equip:
            resolved = _resolve_and_inline(eq_ref, index, inlined)
            if resolved:
                equip_items.append(resolved)
        if equip_items:
            node["bios:labEquipment"] = equip_items

    # computationalTool (ARC profile) — inline
    comp_tools = _ensure_list(entity.get("computationalTool"))
    if comp_tools:
        tool_items = []
        for tool_ref in comp_tools:
            resolved = _resolve_and_inline(tool_ref, index, inlined)
            if resolved:
                tool_items.append(resolved)
        if tool_items:
            node["bios:computationalTool"] = tool_items

    # reagent (ARC profile) — inline
    reagents = _ensure_list(entity.get("reagent"))
    if reagents:
        reagent_items = []
        for r_ref in reagents:
            resolved = _resolve_and_inline(r_ref, index, inlined)
            if resolved:
                reagent_items.append(resolved)
        if reagent_items:
            node["bios:reagent"] = reagent_items

    # Input FormalParameters — inline as schema:object
    inputs = _ensure_list(entity.get("input"))
    if inputs:
        inlined_inputs = []
        for inp in inputs:
            resolved = _resolve_and_inline(inp, index, inlined)
            if resolved:
                inlined_inputs.append(resolved)
        if inlined_inputs:
            node["schema:object"] = inlined_inputs

    # Output FormalParameters — inline as schema:result
    outputs = _ensure_list(entity.get("output"))
    if outputs:
        inlined_outputs = []
        for out in outputs:
            resolved = _resolve_and_inline(out, index, inlined)
            if resolved:
                inlined_outputs.append(resolved)
        if inlined_outputs:
            node["schema:result"] = inlined_outputs

    # hasPart (sub-protocols)
    parts = _ensure_list(entity.get("hasPart"))
    if parts:
        inlined_parts = []
        for part_ref in parts:
            resolved = _resolve_and_inline(part_ref, index, inlined)
            if resolved:
                inlined_parts.append(resolved)
        if inlined_parts:
            node["schema:hasPart"] = inlined_parts

    # subjectOf (e.g., CWL abstract) — inline
    subj = entity.get("subjectOf")
    if subj:
        resolved = _resolve_and_inline(subj, index, inlined)
        if resolved:
            node["schema:subjectOf"] = resolved

    # measurementMethod (ARC profile)
    method = _get_prop(entity, "measurementMethod")
    if method:
        node["schema:measurementMethod"] = method

    # intendedUse (ARC/Bioschemas)
    intended = _get_prop(entity, "intendedUse")
    if intended:
        node["schema:description"] = node.get("schema:description", "") or ""
        if node["schema:description"]:
            node["schema:description"] += f" Intended use: {intended}"
        else:
            node["schema:description"] = f"Intended use: {intended}"

    return node


def _inline_lab_protocol(entity, index, inlined):
    """Inline a LabProtocol as a schema:HowTo methodology node.

    LabProtocols describe how a lab process should be carried out.
    Maps to schema:HowTo in cdifProv (actionProcess target).
    """
    types = _get_types(entity)

    # If it's also a ComputationalWorkflow, use the workflow mapper
    if "ComputationalWorkflow" in types:
        return _inline_workflow(entity, index, inlined)

    node = {
        "@type": ["schema:HowTo"],
    }

    if entity.get("@id"):
        node["@id"] = entity["@id"]

    name = _get_prop(entity, "name", "schema:name")
    if name:
        node["schema:name"] = name

    desc = _get_prop(entity, "description", "schema:description")
    if desc:
        node["schema:description"] = desc

    # labEquipment → bios:labEquipment on the protocol
    lab_equip = _ensure_list(entity.get("labEquipment"))
    if lab_equip:
        equip_items = []
        for eq_ref in lab_equip:
            resolved = _resolve_and_inline(eq_ref, index, inlined)
            if resolved:
                equip_items.append(resolved)
        if equip_items:
            node["bios:labEquipment"] = equip_items

    # computationalTool → bios:computationalTool
    comp_tools = _ensure_list(entity.get("computationalTool"))
    if comp_tools:
        tool_items = []
        for tool_ref in comp_tools:
            resolved = _resolve_and_inline(tool_ref, index, inlined)
            if resolved:
                tool_items.append(resolved)
        if tool_items:
            node["bios:computationalTool"] = tool_items

    # reagent → bios:reagent
    reagents = _ensure_list(entity.get("reagent"))
    if reagents:
        reagent_items = []
        for r_ref in reagents:
            resolved = _resolve_and_inline(r_ref, index, inlined)
            if resolved:
                reagent_items.append(resolved)
        if reagent_items:
            node["bios:reagent"] = reagent_items

    # Input FormalParameters
    inputs = _ensure_list(entity.get("input"))
    if inputs:
        inlined_inputs = []
        for inp in inputs:
            resolved = _resolve_and_inline(inp, index, inlined)
            if resolved:
                inlined_inputs.append(resolved)
        if inlined_inputs:
            node["schema:object"] = inlined_inputs

    # Output FormalParameters
    outputs = _ensure_list(entity.get("output"))
    if outputs:
        inlined_outputs = []
        for out in outputs:
            resolved = _resolve_and_inline(out, index, inlined)
            if resolved:
                inlined_outputs.append(resolved)
        if inlined_outputs:
            node["schema:result"] = inlined_outputs

    return node


def _inline_software(entity, index, inlined):
    """Inline a SoftwareApplication."""
    node = {
        "@type": ["schema:Thing", "schema:SoftwareApplication"],
    }

    if entity.get("@id"):
        node["@id"] = entity["@id"]

    name = _get_prop(entity, "name", "schema:name")
    if name:
        node["schema:name"] = name

    desc = _get_prop(entity, "description", "schema:description")
    if desc:
        node["schema:description"] = desc

    url = _get_prop(entity, "url", "schema:url")
    if url:
        node["schema:url"] = url["@id"] if isinstance(url, dict) and "@id" in url else url

    version = _get_prop(entity, "version", "schema:version")
    if version:
        node["schema:version"] = version

    return node


def _inline_file(entity, index, inlined):
    """Inline a File/MediaObject data entity."""
    types = _get_types(entity)

    # If it's also a ComputationalWorkflow, let _inline_workflow handle it
    if "ComputationalWorkflow" in types:
        return _inline_workflow(entity, index, inlined)

    # If it's a LabProtocol, use that mapper
    if "LabProtocol" in types:
        return _inline_lab_protocol(entity, index, inlined)

    mapped_types = ["schema:MediaObject"]
    if "HowTo" in types:
        mapped_types.append("schema:HowTo")
    if "SoftwareSourceCode" in types:
        mapped_types.append("schema:SoftwareSourceCode")

    node = {"@type": mapped_types}

    if entity.get("@id"):
        node["@id"] = entity["@id"]

    name = _get_prop(entity, "name", "schema:name")
    if name:
        node["schema:name"] = name

    desc = _get_prop(entity, "description", "schema:description")
    if desc:
        node["schema:description"] = desc

    enc = _get_prop(entity, "encodingFormat", "schema:encodingFormat")
    if enc:
        node["schema:encodingFormat"] = enc

    # exampleOfWork → inline the FormalParameter
    example_of = entity.get("exampleOfWork")
    if example_of:
        resolved = _resolve_and_inline(example_of, index, inlined)
        if resolved:
            node["schema:exampleOfWork"] = resolved

    # programmingLanguage (for HowTo/SoftwareSourceCode files)
    prog_lang = entity.get("programmingLanguage")
    if prog_lang:
        resolved = _resolve_and_inline(prog_lang, index, inlined)
        if resolved:
            node["schema:programmingLanguage"] = resolved

    return node


def _inline_parameter(entity, index, inlined):
    """Inline a FormalParameter as a MediaObject.

    FormalParameters define expected inputs/outputs of a workflow.
    Mapped to schema:MediaObject (a CreativeWork) since they represent
    file-like entities and are targets of exampleOfWork.
    """
    node = {
        "@type": ["schema:MediaObject"],
    }

    if entity.get("@id"):
        node["@id"] = entity["@id"]

    name = _get_prop(entity, "name", "schema:name")
    if name:
        node["schema:name"] = name

    desc = _get_prop(entity, "description", "schema:description")
    if desc:
        node["schema:description"] = desc

    # Preserve original type info
    add_type = entity.get("additionalType")
    additional_types = ["bios:FormalParameter"]
    if add_type:
        additional_types.append(add_type)
    node["schema:additionalType"] = additional_types

    return node


def _inline_sample(entity, index, inlined):
    """Inline a Bioschemas Sample entity.

    Samples are physical/material entities used or produced by lab processes.
    Map to schema:Thing with additionalType indicating Sample.
    """
    node = {
        "@type": ["schema:Thing"],
        "schema:additionalType": ["bios:Sample"],
    }

    if entity.get("@id"):
        node["@id"] = entity["@id"]

    name = _get_prop(entity, "name", "schema:name")
    if name:
        node["schema:name"] = name

    desc = _get_prop(entity, "description", "schema:description")
    if desc:
        node["schema:description"] = desc

    ident = _get_prop(entity, "identifier", "schema:identifier")
    if ident:
        node["schema:identifier"] = ident

    return node


def _inline_defined_term(entity, index, inlined):
    """Inline a DefinedTerm entity (typically lab equipment/instruments).

    Maps to schema:Thing with schema:DefinedTerm in additionalType,
    matching cdifProv instrument pattern.
    """
    node = {
        "@type": ["schema:Thing", "schema:DefinedTerm"],
    }

    if entity.get("@id"):
        node["@id"] = entity["@id"]

    name = _get_prop(entity, "name", "schema:name")
    if name:
        node["schema:name"] = name

    desc = _get_prop(entity, "description", "schema:description")
    if desc:
        node["schema:description"] = desc

    ident = _get_prop(entity, "identifier", "schema:identifier")
    if ident:
        node["schema:identifier"] = ident

    url = _get_prop(entity, "url", "schema:url")
    if url:
        node["schema:url"] = url["@id"] if isinstance(url, dict) and "@id" in url else url

    return node


def _inline_agent(entity, index, inlined):
    """Inline a Person or Organization entity."""
    types = _get_types(entity)

    if "Person" in types:
        schema_type = "schema:Person"
    elif "Organization" in types:
        schema_type = "schema:Organization"
    else:
        schema_type = "schema:Thing"

    node = {"@type": [schema_type]}

    if entity.get("@id"):
        node["@id"] = entity["@id"]

    name = _get_prop(entity, "name", "schema:name")
    if name:
        node["schema:name"] = name

    url = _get_prop(entity, "url", "schema:url")
    if url:
        node["schema:url"] = url["@id"] if isinstance(url, dict) and "@id" in url else url

    ident = _get_prop(entity, "identifier", "schema:identifier")
    if ident:
        node["schema:identifier"] = ident

    return node


def _inline_language(entity, index, inlined):
    """Inline a ComputerLanguage."""
    node = {
        "@type": ["schema:ComputerLanguage"],
    }

    if entity.get("@id"):
        node["@id"] = entity["@id"]

    name = _get_prop(entity, "name", "schema:name")
    if name:
        node["schema:name"] = name

    alt = entity.get("alternateName")
    if alt:
        node["schema:alternateName"] = alt

    ident = entity.get("identifier")
    if ident:
        node["schema:identifier"] = ident["@id"] if isinstance(ident, dict) and "@id" in ident else ident

    url = entity.get("url")
    if url:
        node["schema:url"] = url["@id"] if isinstance(url, dict) and "@id" in url else url

    return node


def _inline_creative_work(entity, index, inlined):
    """Inline a generic CreativeWork."""
    node = {"@type": ["schema:CreativeWork"]}

    if entity.get("@id"):
        node["@id"] = entity["@id"]

    name = _get_prop(entity, "name", "schema:name")
    if name:
        node["schema:name"] = name

    desc = _get_prop(entity, "description", "schema:description")
    if desc:
        node["schema:description"] = desc

    return node


def _map_parameter_values(param_values, index, inlined):
    """Map ARC parameterValue array to schema:additionalProperty.

    parameterValue contains actual PropertyValue objects with value/unitText,
    recording the real settings used during execution.
    """
    props = []
    for pv in param_values:
        if not isinstance(pv, dict):
            continue

        prop = {"@type": "schema:PropertyValue"}

        if pv.get("@id"):
            prop["@id"] = pv["@id"]

        name = _get_prop(pv, "name", "schema:name")
        if name:
            prop["schema:name"] = name

        value = _get_prop(pv, "value", "schema:value")
        if value is not None:
            prop["schema:value"] = value

        unit = _get_prop(pv, "unitText", "schema:unitText")
        if unit:
            prop["schema:unitText"] = unit

        # propertyID links back to the FormalParameter definition
        prop_id = pv.get("propertyID")
        if isinstance(prop_id, dict) and "@id" in prop_id:
            prop["schema:propertyID"] = prop_id["@id"]
        elif prop_id:
            prop["schema:propertyID"] = prop_id

        props.append(prop)

    return props


# --- Main activity builder ---

def _build_activity_node(action, index, inlined):
    """Build a top-level activity node with all references inlined.

    The activity is dual-typed ["schema:Action", "prov:Activity"] per cdifProv.
    Original RO-Crate action types preserved in schema:additionalType.
    """
    original_types = _get_types(action)

    activity = {
        "@type": ["schema:Action", "prov:Activity"],
    }

    eid = action.get("@id")
    if eid:
        activity["@id"] = eid
        inlined.add(eid)

    name = _get_prop(action, "name", "schema:name")
    if name:
        activity["schema:name"] = name

    desc = _get_prop(action, "description", "schema:description")
    if desc:
        activity["schema:description"] = desc

    # Preserve all original action types (CreateAction, LabProcess, etc.)
    # Bioschemas types get bios: prefix; schema.org types get schema: prefix
    preserved_types = original_types.intersection(ACTION_TYPES)
    if preserved_types:
        activity["schema:additionalType"] = [
            f"bios:{t}" if t in BIOSCHEMAS_TYPES else f"schema:{t}"
            for t in sorted(preserved_types)
        ]

    # actionStatus — normalize full URI to prefixed form
    status = _get_prop(action, "actionStatus", "schema:actionStatus")
    if status and "CompletedActionStatus" in str(status):
        activity["schema:actionStatus"] = "schema:CompletedActionStatus"
    elif status and "FailedActionStatus" in str(status):
        activity["schema:actionStatus"] = "schema:FailedActionStatus"
    else:
        activity["schema:actionStatus"] = "schema:CompletedActionStatus"

    # Temporal bounds
    start = _get_prop(action, "startTime", "schema:startTime")
    if start:
        activity["schema:startTime"] = start
    end = _get_prop(action, "endTime", "schema:endTime")
    if end:
        activity["schema:endTime"] = end

    # executesLabProtocol (ARC) → bios:executesLabProtocol (methodology)
    # Also set schema:actionProcess for cdifProv compatibility
    protocol_ref = action.get("executesLabProtocol")
    if protocol_ref:
        resolved = _resolve_and_inline(protocol_ref, index, inlined)
        if resolved:
            activity["bios:executesLabProtocol"] = resolved
            activity["schema:actionProcess"] = resolved

    # Instrument — inline
    # For ARC, instrument often points to the LabProtocol (same as
    # executesLabProtocol). If actionProcess already captured it, just ref.
    instruments = _ensure_list(action.get("instrument"))
    if instruments:
        inlined_insts = []
        for inst_ref in instruments:
            resolved = _resolve_and_inline(inst_ref, index, inlined)
            if resolved:
                inlined_insts.append(resolved)
        if len(inlined_insts) == 1:
            activity["schema:instrument"] = inlined_insts[0]
        elif inlined_insts:
            activity["schema:instrument"] = inlined_insts

    # Inputs (object) → prov:used — inline
    objects = _ensure_list(action.get("object"))
    if objects:
        used_items = []
        for obj_ref in objects:
            resolved = _resolve_and_inline(obj_ref, index, inlined)
            if resolved:
                used_items.append(resolved)
        if used_items:
            activity["prov:used"] = used_items

    # Outputs (result) → schema:result — inline
    results = _ensure_list(action.get("result"))
    if results:
        result_items = []
        for res_ref in results:
            resolved = _resolve_and_inline(res_ref, index, inlined)
            if resolved:
                result_items.append(resolved)
        if result_items:
            activity["schema:result"] = result_items

    # parameterValue (ARC) → bios:parameterValue (also mapped to schema:additionalProperty)
    param_vals = _ensure_list(action.get("parameterValue"))
    if param_vals:
        props = _map_parameter_values(param_vals, index, inlined)
        if props:
            activity["bios:parameterValue"] = props
            activity["schema:additionalProperty"] = props

    # Agent — inline
    agents = _ensure_list(_get_prop(action, "agent", "schema:agent"))
    if agents:
        agent_items = []
        for ag_ref in agents:
            resolved = _resolve_and_inline(ag_ref, index, inlined)
            if resolved:
                agent_items.append(resolved)
        if len(agent_items) == 1:
            activity["schema:agent"] = agent_items[0]
        elif agent_items:
            activity["schema:agent"] = agent_items

    # Error
    error = _get_prop(action, "error", "schema:error")
    if error:
        activity["schema:error"] = error
        activity["schema:actionStatus"] = "schema:FailedActionStatus"

    return activity


def convert_wrroc_to_cdifprov(doc, verbose=False):
    """Convert a WRROC document to a CDIF provenance @graph document.

    Output @graph contains one nested node per action. Referenced entities
    are inlined at first occurrence and referenced by @id thereafter.
    """
    graph = doc.get("@graph", [])
    if not graph:
        raise ValueError("No @graph found in document")

    index = _build_entity_index(graph)

    # Find all action entities
    actions = [e for e in graph if _get_types(e).intersection(ACTION_TYPES)]
    if not actions:
        raise ValueError("No execution actions found in @graph")

    if verbose:
        print(f"Found {len(actions)} action(s)", file=sys.stderr)

    # Track which @ids have been inlined (shared across all activities)
    inlined = set()
    activity_nodes = []

    for action in actions:
        name = _get_prop(action, "name", "schema:name") or action.get("@id", "unnamed")
        if verbose:
            print(f"  Building: {name}", file=sys.stderr)
        node = _build_activity_node(action, index, inlined)
        activity_nodes.append(node)

    if verbose:
        print(f"\nOutput: {len(activity_nodes)} activity node(s)", file=sys.stderr)

    return {
        "@context": CDIF_PROV_CONTEXT,
        "@graph": activity_nodes,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Convert Workflow Run RO-Crate to CDIF cdifProv activity nodes",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Convert and print to stdout
  python WRROCToCdifProv.py my-rocrate.json

  # Convert and save
  python WRROCToCdifProv.py my-rocrate.json -o prov-output.json

  # Verbose output
  python WRROCToCdifProv.py my-rocrate.json -o prov.json -v
""",
    )
    parser.add_argument("input", help="Input RO-Crate JSON-LD file")
    parser.add_argument("-o", "--output", help="Write output to file")
    parser.add_argument("-v", "--verbose", action="store_true", help="Show progress")

    args = parser.parse_args()

    try:
        if args.verbose:
            print(f"Loading: {args.input}", file=sys.stderr)
        with open(args.input, "r", encoding="utf-8") as f:
            doc = json.load(f)

        result = convert_wrroc_to_cdifprov(doc, verbose=args.verbose)

        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                json.dump(result, f, indent=2)
            if args.verbose:
                print(f"\nOutput written to: {args.output}", file=sys.stderr)
        else:
            print(json.dumps(result, indent=2))

        if args.verbose:
            print("Done!", file=sys.stderr)

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
