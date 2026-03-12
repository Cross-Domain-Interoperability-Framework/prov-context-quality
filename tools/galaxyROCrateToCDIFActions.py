#!/usr/bin/env python3
"""
Galaxy RO-Crate to CDIF Provenance Converter — Multi-Activity Approach

Reads a Galaxy Workflow Run RO-Crate (zip or directory) and produces a
CDIF cdifProv document where each workflow step is a separate prov:Activity.

This is the alternative to the HowTo/step approach in galaxyROCrateToCDIF.py.
Instead of embedding steps as schema:HowToStep within a single activity's
schema:actionProcess, each CWL step becomes its own [schema:Action, prov:Activity]
node with explicit data-flow links between steps.

Output structure:
  - @graph contains:
    - OrganizeAction → Galaxy engine activity
    - CreateAction → top-level workflow execution (references sub-activities)
    - One prov:Activity per workflow step, linked by:
      - prov:wasInformedBy → upstream step activities
      - prov:used → input entities (from upstream step outputs or workflow inputs)
      - schema:result → output entities
      - schema:instrument → tool used for that step
  - Step activities link back to the top-level CreateAction via prov:wasInfluencedBy

Usage:
    python galaxyROCrateToCDIFActions.py Paper_1_Pt3Sn.rocrate.zip -o output.json
    python galaxyROCrateToCDIFActions.py Paper_1_Pt3Sn.rocrate.zip -v
    python galaxyROCrateToCDIFActions.py /path/to/extracted/crate/ -o output.json

References:
    - Workflow Run RO-Crate: https://w3id.org/ro/wfrun/workflow/0.5
    - Galaxy RO-Crate examples: https://zenodo.org/records/13842780
    - CDIF cdifProv: https://github.com/usgin/metadataBuildingBlocks
"""

import json
import argparse
import sys
import zipfile
import os
from pathlib import Path
from collections import OrderedDict, defaultdict

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False


# CDIF output context
CDIF_PROV_CONTEXT = {
    "schema": "http://schema.org/",
    "prov": "http://www.w3.org/ns/prov#",
    "bios": "https://bioschemas.org/",
}

# Galaxy infrastructure files to skip
SKIP_SUFFIXES = ("_attrs.txt", ".provenance")
SKIP_IDS = {"ro-crate-metadata.json", "ro-crate-metadata.jsonld", "./"}
PROFILE_PREFIXES = ("https://w3id.org/ro/", "https://w3id.org/workflowhub/")


# --- Crate reading (shared with galaxyROCrateToCDIF.py) ---

def _read_crate_files(input_path):
    """Read relevant files from a zip or directory."""
    files = {}
    input_path = Path(input_path)

    if input_path.suffix == ".zip" or zipfile.is_zipfile(str(input_path)):
        with zipfile.ZipFile(str(input_path), "r") as zf:
            for name in zf.namelist():
                if name == "ro-crate-metadata.json":
                    files[name] = zf.read(name).decode("utf-8")
                elif name.startswith("workflows/"):
                    files[name] = zf.read(name).decode("utf-8")
                elif name == "jobs_attrs.txt":
                    files[name] = zf.read(name).decode("utf-8")
                elif name == "invocation_attrs.txt":
                    files[name] = zf.read(name).decode("utf-8")
    elif input_path.is_dir():
        meta = input_path / "ro-crate-metadata.json"
        if meta.exists():
            files["ro-crate-metadata.json"] = meta.read_text(encoding="utf-8")
        wf_dir = input_path / "workflows"
        if wf_dir.is_dir():
            for f in wf_dir.iterdir():
                files[f"workflows/{f.name}"] = f.read_text(encoding="utf-8")
        for attr_file in ("jobs_attrs.txt", "invocation_attrs.txt"):
            p = input_path / attr_file
            if p.exists():
                files[attr_file] = p.read_text(encoding="utf-8")
    else:
        raise ValueError(f"Input must be a .zip file or directory: {input_path}")

    if "ro-crate-metadata.json" not in files:
        raise ValueError("No ro-crate-metadata.json found in crate")

    return files


# --- Metadata parsing helpers ---

def _get_types(entity):
    t = entity.get("@type", [])
    if isinstance(t, str):
        t = [t]
    return set(t)


def _ensure_list(val):
    if val is None:
        return []
    if isinstance(val, list):
        return val
    return [val]


def _get_prop(entity, *names):
    for name in names:
        val = entity.get(name)
        if val is not None:
            return val
    return None


def _build_entity_index(graph):
    return {e["@id"]: e for e in graph if "@id" in e}


def _should_skip(eid):
    if eid in SKIP_IDS:
        return True
    if any(eid.startswith(p) for p in PROFILE_PREFIXES):
        return True
    if any(eid.endswith(s) for s in SKIP_SUFFIXES):
        return True
    return False


# --- CWL step parsing ---

def _parse_cwl_steps(cwl_text):
    """Parse abstract CWL to extract ordered step definitions.

    Returns list of dicts: [{name, inputs, outputs, sources}, ...]
    """
    if not HAS_YAML:
        return []

    try:
        cwl = yaml.safe_load(cwl_text)
    except Exception:
        return []

    if not isinstance(cwl, dict) or "steps" not in cwl:
        return []

    steps = []
    raw_steps = cwl["steps"]

    for step_name, step_def in raw_steps.items():
        step = {
            "name": step_name,
            "inputs": {},
            "outputs": [],
            "sources": [],
            "source_steps": set(),
        }

        # Parse input bindings
        in_bindings = step_def.get("in", {})
        if isinstance(in_bindings, dict):
            for param_name, binding in in_bindings.items():
                if isinstance(binding, dict):
                    source = binding.get("source")
                else:
                    source = binding
                step["inputs"][param_name] = source
                if source:
                    sources = source if isinstance(source, list) else [source]
                    step["sources"].extend(sources)
                    # Track which steps feed into this one
                    for s in sources:
                        if isinstance(s, str) and "/" in s:
                            step["source_steps"].add(s.split("/")[0])

        # Parse outputs
        out_list = step_def.get("out", [])
        if isinstance(out_list, list):
            for out in out_list:
                if isinstance(out, str):
                    step["outputs"].append(out)
                elif isinstance(out, dict) and "id" in out:
                    step["outputs"].append(out["id"])

        steps.append(step)

    return steps


# --- Galaxy workflow YAML parsing ---

def _parse_gxwf_inputs(gxwf_text):
    if not HAS_YAML:
        return {}

    try:
        gxwf = yaml.safe_load(gxwf_text)
    except Exception:
        return {}

    inputs = {}
    raw_inputs = gxwf.get("inputs", {})
    for name, defn in raw_inputs.items():
        inputs[name] = {
            "type": defn.get("type", "data"),
            "format": defn.get("format", []),
            "default": defn.get("default"),
            "optional": defn.get("optional", False),
        }
    return inputs


# --- Jobs parsing ---

def _parse_jobs(jobs_text):
    try:
        jobs = json.loads(jobs_text)
    except Exception:
        return []

    tool_jobs = []
    skip_tools = {"__DATA_FETCH__", "upload1", "__MERGE_COLLECTION__",
                  "__UNZIP_COLLECTION__", "__ZIP_COLLECTION__",
                  "__FILTER_FAILED_DATASETS__", "__FILTER_EMPTY_DATASETS__"}

    for j in jobs:
        tool_id = j.get("tool_id", "")
        if tool_id in skip_tools:
            continue
        tool_jobs.append({
            "tool_id": tool_id,
            "tool_version": j.get("tool_version", ""),
            "state": j.get("state", ""),
            "create_time": j.get("create_time", ""),
            "update_time": j.get("update_time", ""),
            "galaxy_version": j.get("galaxy_version", ""),
            "params": j.get("params", {}),
            "input_dataset_mapping": j.get("input_dataset_mapping", {}),
            "output_dataset_mapping": j.get("output_dataset_mapping", {}),
        })

    return tool_jobs


# --- Tool name extraction ---

def _short_tool_name(tool_id):
    parts = tool_id.split("/")
    for i, p in enumerate(parts):
        if p.startswith("0.") or p.startswith("1.") or "+" in p:
            if i > 0:
                return parts[i - 1]
    return parts[-1] if parts else tool_id


# --- Match CWL steps to Galaxy jobs ---

def _match_steps_to_jobs(cwl_steps, tool_jobs):
    """Best-effort matching of CWL steps to Galaxy job records.

    First tries pattern-based matching by tool name.  When that leaves
    too many steps unmatched (e.g. CWL steps are just numbered 1, 2, 3),
    falls back to 1:1 positional matching.
    """
    job_pool = defaultdict(list)
    for job in tool_jobs:
        short = _short_tool_name(job["tool_id"])
        job_pool[short].append(job)

    TOOL_PATTERNS = {
        "larch_athena": ["Extract", "Merge"],
        "larch_feff": ["FEFF"],
        "larch_lcf": ["LCF"],
        "larch_plot": ["Plot", "XANES"],
        "larch_select_paths": ["select", "41"],
        "larch_artemis": ["Artemis"],
    }

    matched = []
    for step in cwl_steps:
        step_name = step["name"]
        job = None

        for tool_name, patterns in TOOL_PATTERNS.items():
            if any(p.lower() in step_name.lower() for p in patterns):
                if job_pool[tool_name]:
                    job = job_pool[tool_name].pop(0)
                    break

        matched.append((step, job))

    # If pattern matching left most steps unmatched, fall back to positional
    matched_count = sum(1 for _, j in matched if j is not None)
    if matched_count < len(matched) // 2 and len(tool_jobs) == len(cwl_steps):
        matched = [(step, job) for step, job in zip(cwl_steps, tool_jobs)]

    return matched


def _build_job_data_flow(tool_jobs):
    """Build data-flow maps from Galaxy job dataset mappings.

    Returns:
        producer: dict mapping dataset_id -> (job_index, output_name)
        job_inputs: list of lists, one per job, each entry is
                    (input_name, dataset_id, source_job_index_or_None, source_output_name)
        job_outputs: list of lists, one per job, each entry is
                     (output_name, dataset_id)
    """
    producer = {}  # dataset_id -> (job_index, output_name)
    job_outputs = []
    for i, job in enumerate(tool_jobs):
        outputs = []
        for out_name, ds_ids in job.get("output_dataset_mapping", {}).items():
            for ds_id in ds_ids:
                # Clean up Galaxy collection output names
                clean_name = out_name
                if clean_name.startswith("__new_primary_file_"):
                    clean_name = clean_name[len("__new_primary_file_"):]
                if clean_name.endswith("__"):
                    clean_name = clean_name[:-2]
                producer[ds_id] = (i, clean_name)
                outputs.append((clean_name, ds_id))
        job_outputs.append(outputs)

    job_inputs = []
    for i, job in enumerate(tool_jobs):
        inputs = []
        for in_name, ds_ids in job.get("input_dataset_mapping", {}).items():
            for ds_id in ds_ids:
                src = producer.get(ds_id)
                if src:
                    inputs.append((in_name, ds_id, src[0], src[1]))
                else:
                    inputs.append((in_name, ds_id, None, None))
        job_inputs.append(inputs)

    return producer, job_inputs, job_outputs


# --- Parameter extraction from Galaxy jobs ---

def _extract_meaningful_params(job):
    if not job or not job.get("params"):
        return []

    skip_params = {
        "__input_ext", "__workflow_invocation_uuid__", "chromInfo",
        "dbkey", "annotation", "zip_outputs", "plot_graph",
    }

    params = job["params"]
    result = []

    def _walk_params(obj, prefix=""):
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k.startswith("__") or k in skip_params:
                    continue
                full_key = f"{prefix}.{k}" if prefix else k

                if isinstance(v, dict):
                    if "__class__" in v or "values" in v:
                        continue
                    if "__current_case__" in v:
                        _walk_params(v, full_key)
                        continue
                    _walk_params(v, full_key)
                elif isinstance(v, list):
                    for i, item in enumerate(v):
                        if isinstance(item, dict):
                            _walk_params(item, f"{full_key}[{i}]")
                elif v is not None and str(v).strip() and str(v) != "?":
                    result.append({"name": full_key, "value": v})

        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                if isinstance(item, dict):
                    _walk_params(item, f"{prefix}[{i}]")

    _walk_params(params)
    return result


def _compact_params_to_properties(flat_params):
    """Compact flat dot-separated params into PropertyValue nodes.

    Groups params sharing a common prefix into schema:StructuredValue
    objects for more compact, readable output.
    """
    if not flat_params:
        return []

    def _convert_val(v):
        try:
            v = float(v)
            if v == int(v):
                v = int(v)
        except (ValueError, TypeError):
            pass
        return v

    # Build tree from dot-separated names
    root = {}
    for p in flat_params:
        parts = p["name"].split(".")
        node = root
        ok = True
        for part in parts[:-1]:
            if part not in node:
                node[part] = {}
            elif not isinstance(node[part], dict):
                ok = False
                break
            node = node[part]
        if ok:
            node[parts[-1]] = _convert_val(p["value"])
        else:
            root[p["name"]] = _convert_val(p["value"])

    def _emit(tree, prefix):
        results = []
        for key in tree:
            val = tree[key]
            name = f"{prefix}.{key}" if prefix else key
            if not isinstance(val, dict):
                results.append({
                    "@type": "schema:PropertyValue",
                    "schema:name": name,
                    "schema:value": val,
                })
            elif len(val) >= 2:
                sv = {"@type": "schema:StructuredValue"}
                _flatten_sv(val, "", sv)
                results.append({
                    "@type": "schema:PropertyValue",
                    "schema:name": name,
                    "schema:value": sv,
                })
            else:
                results.extend(_emit(val, name))
        return results

    def _flatten_sv(tree, prefix, sv):
        for key in tree:
            val = tree[key]
            subkey = f"{prefix}.{key}" if prefix else key
            if isinstance(val, dict):
                if len(val) >= 2:
                    nested = {"@type": "schema:StructuredValue"}
                    _flatten_sv(val, "", nested)
                    sv[subkey] = nested
                else:
                    _flatten_sv(val, subkey, sv)
            else:
                sv[subkey] = val

    return _emit(root, "")


# --- Build file reference nodes ---

def _build_file_ref(entity):
    node = {"@type": ["schema:MediaObject"]}

    eid = entity.get("@id", "")
    if eid:
        node["@id"] = eid

    name = _get_prop(entity, "name", "schema:name")
    if name:
        node["schema:name"] = name

    desc = _get_prop(entity, "description", "schema:description")
    if desc:
        node["schema:description"] = desc

    enc = _get_prop(entity, "encodingFormat", "schema:encodingFormat")
    if enc:
        node["schema:encodingFormat"] = enc

    add_type = entity.get("additionalType")
    if add_type:
        at = add_type if isinstance(add_type, list) else [add_type]
        node["schema:additionalType"] = ["bios:FormalParameter"] + at

    return node


def _build_collection_ref(entity, index):
    node = {"@type": ["schema:CreativeWorkSeries"]}

    eid = entity.get("@id", "")
    if eid:
        node["@id"] = eid

    name = _get_prop(entity, "name", "schema:name")
    if name:
        node["schema:name"] = name

    parts = _ensure_list(entity.get("hasPart", []))
    if parts:
        node["schema:description"] = f"Collection of {len(parts)} items"

    return node


# --- Build per-step activity nodes ---

def _build_step_activity(step, job, position, step_id_map, parent_id=None,
                         job_index=None, job_inputs=None, job_outputs=None,
                         matched_steps=None):
    """Build a prov:Activity node for a single workflow step.

    Args:
        step: CWL step definition dict
        job: matched Galaxy job dict (or None)
        position: 1-based step position
        step_id_map: dict mapping step name -> activity @id for cross-references
        parent_id: @id of the parent CreateAction activity
        job_index: index of this job in tool_jobs list (for data flow lookup)
        job_inputs: per-job input list from _build_job_data_flow
        job_outputs: per-job output list from _build_job_data_flow
        matched_steps: full list of (step, job) tuples for resolving cross-refs
    """
    step_name = step["name"]
    act_id = step_id_map[step_name]

    node = {
        "@type": ["schema:Action", "prov:Activity"],
        "@id": act_id,
        "schema:name": step_name,
        "schema:additionalType": ["schema:CreateAction"],
        "schema:actionStatus": "schema:CompletedActionStatus",
        "schema:position": position,
    }

    # Link to parent workflow activity
    if parent_id:
        node["prov:wasInfluencedBy"] = {"@id": parent_id}

    # Timestamps from job
    if job:
        if job.get("create_time"):
            node["schema:startTime"] = job["create_time"]
        if job.get("update_time"):
            node["schema:endTime"] = job["update_time"]

    # Tool as instrument
    if job:
        tool_id = job.get("tool_id", "")
        tool_version = job.get("tool_version", "")
        short_name = _short_tool_name(tool_id)
        inst = {
            "@type": ["schema:SoftwareApplication"],
            "schema:name": short_name,
        }
        if tool_version:
            inst["schema:version"] = tool_version
        if tool_id:
            inst["schema:identifier"] = tool_id
        node["schema:instrument"] = inst

    # --- Data flow ---
    # Use CWL sources for prov:wasInformedBy and prov:used when available;
    # fall back to Galaxy job dataset mappings otherwise.
    # For schema:result, always prefer CWL outputs but fall back to jobs.
    has_cwl_sources = bool(step.get("source_steps") or step.get("sources"))
    has_cwl_outputs = bool(step.get("outputs"))
    has_job_flow = (job_index is not None and job_inputs and job_outputs)

    # Build job_to_step index for resolving upstream refs
    job_to_step = {}
    if has_job_flow and matched_steps:
        for i, (s, j) in enumerate(matched_steps):
            if j is not None:
                job_to_step[i] = step_id_map.get(s["name"])

    # --- prov:wasInformedBy and prov:used ---
    if has_cwl_sources:
        # CWL-based input flow
        source_steps = step.get("source_steps", set())
        if source_steps:
            informed_by = []
            for src in sorted(source_steps):
                if src in step_id_map:
                    informed_by.append({"@id": step_id_map[src]})
            if informed_by:
                node["prov:wasInformedBy"] = informed_by

        sources = step.get("sources", [])
        if sources:
            used_refs = []
            for s in sources:
                if isinstance(s, str):
                    if "/" in s:
                        src_step, src_output = s.split("/", 1)
                        used_refs.append({
                            "@type": "schema:Thing",
                            "@id": f"#output-{src_step}-{src_output}",
                            "schema:name": f"{src_step}/{src_output}",
                        })
                    else:
                        used_refs.append({
                            "@type": "schema:Thing",
                            "@id": f"#input-{s}",
                            "schema:name": s,
                        })
            if used_refs:
                node["prov:used"] = used_refs

    elif has_job_flow:
        # Job-based input flow from Galaxy dataset mappings
        inputs = job_inputs[job_index] if job_index < len(job_inputs) else []
        if inputs:
            informed_set = set()
            used_refs = []
            for in_name, ds_id, src_job_idx, src_out_name in inputs:
                if src_job_idx is not None and src_job_idx in job_to_step:
                    informed_set.add(src_job_idx)
                    src_step_id = job_to_step[src_job_idx]
                    src_step_name = matched_steps[src_job_idx][0]["name"] \
                        if src_job_idx < len(matched_steps) else f"job-{src_job_idx}"
                    used_refs.append({
                        "@type": "schema:Thing",
                        "@id": f"{src_step_id}/output-{src_out_name}",
                        "schema:name": f"{src_step_name}/{src_out_name}",
                    })
                else:
                    used_refs.append({
                        "@type": "schema:Thing",
                        "@id": f"#external-{ds_id[:12]}",
                        "schema:name": f"workflow input ({in_name})",
                    })

            if informed_set:
                informed_by = []
                for idx in sorted(informed_set):
                    if idx in job_to_step:
                        informed_by.append({"@id": job_to_step[idx]})
                node["prov:wasInformedBy"] = informed_by

            seen = set()
            deduped = []
            for ref in used_refs:
                if ref["@id"] not in seen:
                    seen.add(ref["@id"])
                    deduped.append(ref)
            if deduped:
                node["prov:used"] = deduped

    # --- schema:result ---
    if has_cwl_outputs:
        outputs = step.get("outputs", [])
        result_refs = []
        for out in outputs:
            result_refs.append({
                "@type": "schema:Thing",
                "@id": f"#output-{step_name}-{out}",
                "schema:name": f"{step_name}/{out}",
            })
        if result_refs:
            node["schema:result"] = result_refs

    elif has_job_flow:
        # Job-based outputs from Galaxy dataset mappings
        outputs = job_outputs[job_index] if job_index < len(job_outputs) else []
        if outputs:
            result_refs = []
            seen = set()
            for out_name, ds_id in outputs:
                ref_id = f"{act_id}/output-{out_name}"
                if ref_id not in seen:
                    seen.add(ref_id)
                    result_refs.append({
                        "@type": "schema:Thing",
                        "@id": ref_id,
                        "schema:name": f"{step_name}/{out_name}",
                    })
            if result_refs:
                node["schema:result"] = result_refs

    # Parameters as schema:additionalProperty — compact into StructuredValue groups
    if job:
        meaningful = _extract_meaningful_params(job)
        props = _compact_params_to_properties(meaningful)
        if props:
            node["schema:additionalProperty"] = props

    return node


# --- Main conversion ---

def convert_galaxy_crate_actions(input_path, verbose=False):
    """Convert a Galaxy RO-Crate to CDIF cdifProv with per-step activities."""

    if verbose:
        print(f"Reading crate: {input_path}", file=sys.stderr)

    crate_files = _read_crate_files(input_path)

    # Parse ro-crate-metadata.json
    metadata = json.loads(crate_files["ro-crate-metadata.json"])
    graph = metadata.get("@graph", [])
    index = _build_entity_index(graph)

    # Find actions
    action_types = {"CreateAction", "OrganizeAction"}
    actions = [e for e in graph if _get_types(e).intersection(action_types)]

    if verbose:
        print(f"Found {len(actions)} action(s) in metadata", file=sys.stderr)

    # Parse CWL abstract workflow
    cwl_steps = []
    for fname, content in crate_files.items():
        if fname.endswith(".abstract.cwl"):
            if verbose:
                print(f"Parsing CWL steps from {fname}", file=sys.stderr)
            cwl_steps = _parse_cwl_steps(content)
            if verbose:
                print(f"  Found {len(cwl_steps)} CWL steps", file=sys.stderr)
            break

    # Parse Galaxy workflow YAML
    gxwf_inputs = {}
    for fname, content in crate_files.items():
        if fname.endswith(".gxwf.yml"):
            if verbose:
                print(f"Parsing Galaxy workflow from {fname}", file=sys.stderr)
            gxwf_inputs = _parse_gxwf_inputs(content)
            if verbose:
                print(f"  Found {len(gxwf_inputs)} workflow inputs", file=sys.stderr)
            break

    # Parse Galaxy jobs
    tool_jobs = []
    if "jobs_attrs.txt" in crate_files:
        if verbose:
            print("Parsing Galaxy job records", file=sys.stderr)
        tool_jobs = _parse_jobs(crate_files["jobs_attrs.txt"])
        if verbose:
            print(f"  Found {len(tool_jobs)} tool jobs", file=sys.stderr)

    # Match CWL steps to Galaxy jobs
    matched_steps = []
    if cwl_steps:
        matched_steps = _match_steps_to_jobs(cwl_steps, tool_jobs)
    elif tool_jobs:
        for i, job in enumerate(tool_jobs):
            step = {
                "name": _short_tool_name(job["tool_id"]),
                "inputs": {},
                "outputs": [],
                "sources": [],
                "source_steps": set(),
            }
            matched_steps.append((step, job))

    # Collect unique tools
    tool_set = OrderedDict()
    for job in tool_jobs:
        tid = job["tool_id"]
        short = _short_tool_name(tid)
        if short not in tool_set:
            tool_set[short] = {
                "tool_id": tid,
                "version": job.get("tool_version", ""),
            }

    # Build step ID map for cross-references
    step_id_map = {}
    for i, (step, _job) in enumerate(matched_steps):
        step_id_map[step["name"]] = f"#step-{i+1}-{step['name'].replace(' ', '-')}"

    # Build output nodes
    activity_nodes = []

    for action in actions:
        types = _get_types(action)
        is_organize = "OrganizeAction" in types
        is_create = "CreateAction" in types

        node = {
            "@type": ["schema:Action", "prov:Activity"],
        }

        eid = action.get("@id")
        if eid:
            node["@id"] = eid

        name = _get_prop(action, "name", "schema:name")
        if name:
            node["schema:name"] = name

        desc = _get_prop(action, "description", "schema:description")
        if desc:
            node["schema:description"] = desc

        if is_organize:
            node["schema:additionalType"] = ["schema:OrganizeAction"]
        elif is_create:
            node["schema:additionalType"] = ["schema:CreateAction"]

        # Status
        status = _get_prop(action, "actionStatus")
        if status and "Completed" in str(status):
            node["schema:actionStatus"] = "schema:CompletedActionStatus"
        elif status and "Failed" in str(status):
            node["schema:actionStatus"] = "schema:FailedActionStatus"
        else:
            node["schema:actionStatus"] = "schema:CompletedActionStatus"

        # Timestamps
        start = _get_prop(action, "startTime")
        if start:
            node["schema:startTime"] = start
        end = _get_prop(action, "endTime")
        if end:
            node["schema:endTime"] = end

        # OrganizeAction: Galaxy engine instrument
        if is_organize:
            inst_ref = action.get("instrument")
            if isinstance(inst_ref, dict) and "@id" in inst_ref:
                inst_entity = index.get(inst_ref["@id"])
                if inst_entity:
                    inst_node = {
                        "@type": ["schema:SoftwareApplication"],
                        "schema:name": _get_prop(inst_entity, "name", "schema:name") or "Galaxy",
                    }
                    version = _get_prop(inst_entity, "version")
                    if version:
                        inst_node["schema:version"] = version
                    url = _get_prop(inst_entity, "url")
                    if url:
                        inst_node["schema:url"] = url
                    node["schema:instrument"] = inst_node

            if tool_jobs:
                gv = tool_jobs[0].get("galaxy_version")
                if gv:
                    if "schema:instrument" in node:
                        node["schema:instrument"]["schema:version"] = gv
                    else:
                        node["schema:instrument"] = {
                            "@type": ["schema:SoftwareApplication"],
                            "schema:name": "Galaxy workflow engine",
                            "schema:version": gv,
                        }

        # CreateAction: workflow instrument reference
        if is_create and matched_steps:
            inst_ref = action.get("instrument")
            wf_name = name
            if isinstance(inst_ref, dict) and "@id" in inst_ref:
                wf_entity = index.get(inst_ref["@id"])
                if wf_entity:
                    wf_name = _get_prop(wf_entity, "name", "schema:name") or name
                    node["schema:instrument"] = {
                        "@type": ["schema:SoftwareApplication"],
                        "schema:additionalType": ["bios:ComputationalWorkflow"],
                        "schema:name": wf_name,
                        "@id": wf_entity.get("@id"),
                    }

        # Inputs (object) → prov:used
        if is_create:
            objects = _ensure_list(action.get("object"))
            if objects:
                used_items = []
                for obj_ref in objects:
                    ref_id = obj_ref.get("@id") if isinstance(obj_ref, dict) else obj_ref
                    if ref_id and not _should_skip(ref_id):
                        entity = index.get(ref_id)
                        if entity:
                            etypes = _get_types(entity)
                            if "Collection" in etypes:
                                used_items.append(_build_collection_ref(entity, index))
                            else:
                                used_items.append(_build_file_ref(entity))
                        else:
                            used_items.append({"@type": "schema:Thing", "@id": ref_id})
                if used_items:
                    node["prov:used"] = used_items

            # Results
            results = _ensure_list(action.get("result"))
            if results:
                result_items = []
                for res_ref in results:
                    ref_id = res_ref.get("@id") if isinstance(res_ref, dict) else res_ref
                    if ref_id and not _should_skip(ref_id):
                        entity = index.get(ref_id)
                        if entity:
                            etypes = _get_types(entity)
                            if "Collection" in etypes:
                                result_items.append(_build_collection_ref(entity, index))
                            else:
                                result_items.append(_build_file_ref(entity))
                        else:
                            result_items.append({"@type": "schema:Thing", "@id": ref_id})
                if result_items:
                    node["schema:result"] = result_items

        # Agent
        agent_refs = _ensure_list(_get_prop(action, "agent"))
        if agent_refs:
            for ag_ref in agent_refs:
                ref_id = ag_ref.get("@id") if isinstance(ag_ref, dict) else ag_ref
                if ref_id:
                    ag_entity = index.get(ref_id)
                    if ag_entity:
                        ag_types = _get_types(ag_entity)
                        ag_node = {}
                        if "Person" in ag_types:
                            ag_node["@type"] = ["schema:Person"]
                        elif "Organization" in ag_types:
                            ag_node["@type"] = ["schema:Organization"]
                        else:
                            ag_node["@type"] = ["schema:Thing"]
                        ag_name = _get_prop(ag_entity, "name")
                        if ag_name:
                            ag_node["schema:name"] = ag_name
                        node["schema:agent"] = ag_node

        if verbose:
            print(f"  Built: {node.get('schema:name', 'unnamed')}", file=sys.stderr)

        activity_nodes.append(node)

    # Find the CreateAction @id for parent linking
    create_action_id = None
    for node in activity_nodes:
        if "schema:CreateAction" in node.get("schema:additionalType", []):
            create_action_id = node.get("@id")
            break

    # Build job data flow maps for fallback when CWL lacks output declarations
    _producer, ji, jo = _build_job_data_flow(tool_jobs)

    # Map matched_steps job indices back to tool_jobs indices
    job_index_map = {}
    for i, (step, job) in enumerate(matched_steps):
        if job is not None:
            for ti, tj in enumerate(tool_jobs):
                if tj is job:
                    job_index_map[i] = ti
                    break

    # Build per-step activity nodes
    step_activities = []
    for i, (step, job) in enumerate(matched_steps):
        tj_idx = job_index_map.get(i)
        step_node = _build_step_activity(
            step, job, i + 1, step_id_map, create_action_id,
            job_index=tj_idx, job_inputs=ji, job_outputs=jo,
            matched_steps=matched_steps,
        )
        step_activities.append(step_node)

        if verbose and i == 0:
            print(f"  Building {len(matched_steps)} step activities...",
                  file=sys.stderr)

    if verbose:
        print(f"\nOutput: {len(activity_nodes)} top-level activity node(s), "
              f"{len(step_activities)} step activity node(s)", file=sys.stderr)

    # Combine: top-level activities first, then step activities
    all_nodes = activity_nodes + step_activities

    return {
        "@context": CDIF_PROV_CONTEXT,
        "@graph": all_nodes,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Convert Galaxy RO-Crate to CDIF cdifProv with per-step activities",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Convert a zip and save
  python galaxyROCrateToCDIFActions.py Paper_1_Pt3Sn.rocrate.zip -o output.json

  # Convert an extracted directory
  python galaxyROCrateToCDIFActions.py /path/to/crate/ -o output.json -v

  # Print to stdout
  python galaxyROCrateToCDIFActions.py my-crate.zip
""",
    )
    parser.add_argument("input", help="Input RO-Crate zip file or directory")
    parser.add_argument("-o", "--output", help="Write output to file")
    parser.add_argument("-v", "--verbose", action="store_true", help="Show progress")

    args = parser.parse_args()

    try:
        result = convert_galaxy_crate_actions(args.input, verbose=args.verbose)

        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            if args.verbose:
                print(f"\nOutput written to: {args.output}", file=sys.stderr)
        else:
            print(json.dumps(result, indent=2, ensure_ascii=False))

        if args.verbose:
            print("Done!", file=sys.stderr)

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
