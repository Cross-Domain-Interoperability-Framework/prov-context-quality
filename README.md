# prov-context-quality

Properties for describing the origin of data, the situation of its creation, and assessment of data quality to inform use.

There is a related [Google drive](https://drive.google.com/drive/folders/1TGToyv72qedgMB5vr8ZImSdn79hH0TMc?usp=drive_link) that contains meeting notes and some other documents.

## Contents

### Documentation

- **[ProvenanceOptions.md](ProvenanceOptions.md)** — Comprehensive comparison of provenance approaches available in CDIF: the three native building blocks (cdifProv, provActivity, ddicdiProv) and external RO-Crate-based profiles (WRROC, ARC). Covers property mappings, multi-step provenance patterns, and guidance for implementing ARC profile support in CDIF.
- **[agents.md](agents.md)** — Analysis of how agents (people, organizations, software) are represented across provenance vocabularies used in CDIF, with recommendations for consistent implementation.

### Ontology Files

- **[PROV_Classes.ttl](PROV_Classes.ttl)** — PROV-based provenance classes as discussed at the Dagstuhl Workshop (November 2025), mapping DDI-CDI provenance activity types to W3C PROV-O. Includes editorial commentary on class naming conventions and agent modeling approaches.
- **[output_uc4 (1).ttl](output_uc4%20(1).ttl)** — PROV-O example: ML model development pipeline (data transformation, model development, model validation) demonstrating `prov:Activity`, `prov:Entity`, and `prov:wasAssociatedWith` patterns.

### Tools

- **[tools/WRROCToCdifProv.py](tools/WRROCToCdifProv.py)** — Converts Workflow Run RO-Crate (WRROC) and ARC Workflow Run RO-Crate files into CDIF cdifProv-compatible `@graph` documents. Supports standard WRROC profiles (Process Run Crate, Workflow Run Crate, Provenance Run Crate) and the ARC profile (LabProcess, LabProtocol, parameterValue, labEquipment, executesLabProtocol). Output uses `bios:` namespace prefix (`https://bioschemas.org/`) for all Bioschemas types and properties.

```bash
# Convert and save
python tools/WRROCToCdifProv.py input-rocrate.json -o output.cdifprov.json

# Verbose output
python tools/WRROCToCdifProv.py input-rocrate.json -o output.cdifprov.json -v

# Print to stdout
python tools/WRROCToCdifProv.py input-rocrate.json
```

### Examples

The [Examples/](Examples/) folder contains provenance instance documents in various formats:

| File | Description |
|---|---|
| `ODIS_provExampleJulesVerne.json` | ODIS/OIH provenance example (schema.org Action pattern) |
| `Bennu-py-GC-MS*.json` | Bennu asteroid py-GC-MS/MS analytical workflow — standard WRROC and ARC profile versions, with source RO-Crates and cdifProv conversions |
| `FeS2-Analysis.*` | Galaxy FeS2 workflow — RO-Crate source and cdifProv conversion |
| `Paper_1_Pt3Sn.*` | Galaxy Pt3Sn catalyst workflow |
| `Paper_2_Diphosphine*.*` | Galaxy Diphosphine workflow |
| `Paper_3-Au-colloids.*` | Galaxy Au colloids workflow |
| `Paper_5-LaMnO3*.*` | Galaxy LaMnO3 catalytic behaviour workflow |
| `Paper_8-EXAFS-fitting.*` | Galaxy EXAFS fitting workflow |

Galaxy workflow RO-Crates originate from [Zenodo record 13842780](https://zenodo.org/records/13842780). All `.cdifprov.json` files were generated using [tools/WRROCToCdifProv.py](tools/WRROCToCdifProv.py).

## Related Repositories

- [usgin/metadataBuildingBlocks](https://github.com/usgin/metadataBuildingBlocks) — CDIF metadata building blocks (cdifProv, provActivity, ddicdiProv schemas and SHACL shapes)
- [Cross-Domain-Interoperability-Framework/packaging](https://github.com/Cross-Domain-Interoperability-Framework/packaging) — CDIF packaging tools including RO-Crate and WRROC converters
- [Cross-Domain-Interoperability-Framework/validation](https://github.com/Cross-Domain-Interoperability-Framework/validation) — CDIF validation schemas and SHACL shapes
