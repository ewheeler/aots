# Separate Semantic Alert Facts From Presentation

Status: Accepted as the next-stage architecture boundary. Schemas, vectors, V1 freezes, raw-identity retention, and independent readiness verification are implemented; V2 runtime and operational activation remain unimplemented and blocked.

## Context

The current dry-run engine separates classification from delivery, but Orchestration Product Facts are organized as `summary`, `situation`, and `forecast`, while the portable renderer still reconstructs facts from generic report fields. Further consultation may change product packaging, section order, content density, languages, hazards, regional composition, and delivery channels.

Adding more templates directly would reproduce the existing coupling across multiple outputs. Building a generic plugin or workflow framework would overcorrect and weaken validation.

## Decision

Introduce one semantic artifact and one controlled presentation boundary:

```text
Orchestration ProductDecision v2 + semantic ProductFactSet v2
  -> checksummed artifact boundary
  -> root PresentationProfile v1
  -> CompositionManifest v1
  -> publication artifacts
```

### ProductFactSet V2

ProductFactSet contains identities, classification evidence, official facts, threat facts, typed modeled metrics, PiN/CHiN semantics, typed hazards, availability, and provenance.

It does not contain sections, headings, prose, actions, contacts, visual placement, packaging, recipients, channels, delivery providers, or mutable lifecycle state.

### Classification Evidence

Classification evidence is a strict discriminated union:

- `OfficialAdvisoryEvidence`
- `ForecastOnlyThreatEvidence`

Forecast-only evidence may support Warning but can never establish Alert. It must not be represented as a partially populated or synthetic official Current Storm State.

The readiness schemas and vectors cover both evidence variants. Future runtime work will emit official-advisory V2 alongside unchanged V1 output; forecast-only output will be native V2 because V1 has no valid representation for it. No V2 producer runtime exists yet.

### Storm Episode Identity

An internal episode ID exists before official genesis. Immutable link events associate a provisional forecast identity with a later official canonical storm ID. Existing history is linked rather than rewritten.

The current `TRACK_ID` audit failed: the field prefers `longStormName` and only falls back to raw ECMWF BUFR `stormIdentifier`. The forecast submodule now retains raw `stormIdentifier` and implements the candidate tuple/normalization specified by [ADR 0011](0011-use-provisional-storm-episode-identity.md) and the machine-readable readiness contracts. It does not generate or persist an episode ID. Storm name, `TRACK_ID`, and forecast time are not candidate-key inputs. Structural retention does not satisfy the historical/provider stability evidence required for operational activation.

### Presentation Profiles

Root owns strict presentation profiles built from a closed set of renderer-owned component IDs and typed options. Profiles may select and order registered components, declare requirements, and specify fail-closed missing-fact behavior.

Profiles cannot contain arbitrary fact paths, expressions, executable hooks, plugins, or unrestricted extension bags.

### Ownership

Orchestration owns evidence normalization, episode identity, threat, classification, Product Decision, semantic Product Facts, lifecycle, and future delivery plans.

Root owns artifact validation, presentation profiles, composition manifests, rendering, and publication.

The cross-repository handshake is versioned, checksummed artifacts only. Root does not re-run classification policy, and Orchestration does not depend on root profile internals. Presentation/profile changes do not change Product Decision identity.

### Versioning

Policy, Product Facts, presentation, composition, content, lifecycle, publication, and delivery versions remain independent. The first tracer introduces ProductDecision v2, ProductFactSet v2, official and provisional Storm Episode identity, immutable Storm Episode Link events, episode-based lifecycle continuity, PresentationProfile v1, CompositionManifest v1, and PublicationManifest v2. Their machine-readable contract/test readiness exists; runtime production and root publication integration do not.

Content releases, lifecycle policy releases, regional composition, private recipient stores, and delivery contracts are added only with their corresponding consultation-approved tracers.

## Migration

- Freeze V1 conformance and claims vectors.
- Keep V1 fixtures and ledgers unchanged.
- Follow the exact canonical-contract, digest, identity, artifact-handshake, parity, and privacy rules in the [Alert Product V2 Readiness Reference](../alert-product-v2-readiness.qmd), [ADR 0011](0011-use-provisional-storm-episode-identity.md), [ADR 0012](0012-use-canonical-content-addressed-alert-artifacts.md), and [ADR 0013](0013-keep-alert-publication-data-minimal.md).
- Add a pure, one-way, fail-closed V1-to-V2 adapter for supported official-advisory cases.
- Emit official-advisory V2 alongside V1 in dry-run memory without changing V1 identities or behavior.
- Emit native forecast-only V2 Warning, no-product, or manual-review outcomes without fabricating a Current Storm State; every forecast-only Alert attempt fails closed.
- Link provisional and official identities through immutable events and preserve one episode-based country lifecycle without rewriting prior history.
- Make root consume checksummed V2 artifacts.
- Reproduce the current long product through one compatibility profile and prove claim parity; semantic claims come only from ProductFactSet, while visual components may use only explicitly referenced checksummed artifacts.
- Remove root report-key reconstruction only after parity passes.

Historical Jerry, Melissa, and Cristina examples become scenario and claim fixtures. Their exact prose, layout, colors, and page structure are not contract authority.

## Consequences

- Product packaging can change without rewriting evidence or classification.
- Email-only, combined, and email-plus-technical-report outputs can consume the same facts.
- New hazard types require reviewed typed schema variants and producers, not template dictionaries.
- Actions, references, locales, and presentation order can change without changing Product Decision identity.
- Root must stop duplicating Orchestration policy validation as V2 adoption progresses.
- ProductFactSet cannot use Summary/Situation/Forecast as its canonical structure.

## Explicit Deferrals

- Snowflake persistence and scheduling
- Recipient directory, outbox, and provider adapters
- Real or shadow sends
- True PDF attachment delivery
- PDF engine choice until a reproducibility spike
- Regional recipient fan-out
- Generic multilingual or plugin systems
- Modeled rainfall/surge impacts
- Legacy cutover

These require later consultation gates and separate safety review.
