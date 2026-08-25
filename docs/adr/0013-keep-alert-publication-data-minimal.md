# Keep Alert Publication Data Minimal

Status: Accepted. Strict controlled-metadata contracts, PublicationManifest v2, publication vectors, and exact public-safe canonical-byte verification are implemented as readiness contracts/tests; HTML/PNG content inspection, root runtime enforcement, source-license approval, and operational publication approval are not.

## Context

Alert inputs may include administrative exposure, child-impact estimates, facilities, precise geometry, tracks, provider identifiers, source references, and future delivery data. A self-contained Snapshot Output Bundle is auditable, but auditability does not make every field suitable for public publication. Public URLs and third-party source access do not by themselves grant redistribution rights.

## Decision

Keep ProductFactSet, source evidence, raw provider identity, and policy evidence `internal_sensitive`; keep Alert Claims `internal_audit`; classify PresentationProfile and allowlisted CompositionManifest/PublicationManifest as `public_metadata`; classify validated rendered HTML/PNG as `public_output`; and label committed conformance data `synthetic_public`. Visual source references are `internal_sensitive` or `partner_restricted`. The exact role/media/path/classification combinations are in the ArtifactReference, ProductFactSet, CompositionManifest, and PublicationManifest schemas.

Exclude recipients, private contacts, provider attempts, and delivery state from ProductFactSet, CompositionManifest, public Snapshot Output Bundle artifacts, and Publication Manifest. Do not expose raw tracks, tiles, geometry, exact coordinates, source URLs/GUIDs, or facility detail in the first tracer. Treat ECMWF source material and raw identifiers as non-public unless explicit reuse and stability evidence is recorded.

Public CompositionManifest component/output records carry no `source_reference_ids`; omissions have only controlled component/reason fields and no arbitrary detail. Omission records correspond exactly to omitted components/reasons, and outputs are HTML first followed by path-sorted visuals. Renderer ID is fixed to `aots-compatibility-renderer`.

PublicationManifest v2 exposes an opaque `case_id`, country/time, one of five allowed comparison/certification/certifying tuples, a checksummed CompositionManifest reference, and ordered checksummed `public_output` HTML/PNG metadata. It has no storm display name. `snapshots_dir` is `snapshots`, and every composition/output path is derived from the matching `case_id`. Its strict schema and vectors reject undeclared metadata, contradictory comparison semantics, cross-case paths, non-public classifications, unsafe paths, and invalid role/media/path combinations. ArtifactReference producer IDs are closed to the machine-schema allowlist.

Publication must fail closed when classification, aggregation safety, source licensing, country-office approval, content inspection, or allowlist validation is unknown. Schemas inspect JSON structure and controlled metadata only; they do not prove that HTML/PNG bytes omit private data, remote resources, or unsafe content. That runtime enforcement is blocking and unimplemented.

## Consequences

- ProductFactSet is bundle-internal by default; PublicationManifest v2 may expose only the schema-defined non-sensitive composition reference.
- Public HTML and aggregate PNGs require parity, accessibility, privacy, and publication approval.
- The schemas do not define retention periods or grant third-party redistribution rights; those remain operational policy gates.
- Adding a public field, artifact role, third-party source, or classification requires a new schema/privacy-policy review.
