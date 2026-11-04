# Ahead of the Storm Open Roadmap

## Objective

Complete a non-sending, artifact-oriented path from operational Product Decision and semantic ProductFactSet through controlled presentation and safe publication, while preserving existing V1 behavior and upstream ownership.

## Azure-First Cloud-Portable Deployment Readiness Milestone

This is a cross-cutting, Azure-first, nonproduction and non-sending readiness umbrella—not a production-launch milestone. Discovery may start in parallel with Active Slices 1–6; V2 runtime completion is not a prerequisite for the synthetic Stage A proof. Slice 7 remains the Stage A execution task; this milestone adds its prerequisites and broader readiness evidence, not a second job. Follow [Cloud Deployment Plan gates 1–3](docs/project/cloud-deployment-plan.qmd#ordered-delivery-and-acceptance-gates) and the reviewed [Azure Alert Execution Plan](docs/project/azure-alert-execution-plan.qmd).

- **Before provisioning or granting data access:** close the cloud-plan inventory/approval gate for actual runtimes, source and storage handoffs, owners/operators, classification/licensing, tenant/region/residency, network, external credentials/quotas, host assumptions, budgets, support, and recovery/SLO objectives. Unknowns block the affected deployment, not become defaults.
- **Resolve the infrastructure convention before provisioning:** the cloud plan proposes OpenTofu, while the reviewed Azure Stage A and subscription plans specify Bicep. Owners must choose and reconcile one convention, state ownership, and protected CI federation; never let competing tools/states manage the same resources.
- **During the milestone:** use approved nonproduction Azure environments to complete Stage A and separately package/measure forecast, impact, Data API, and dashboard workloads with synthetic/non-sensitive data. Prove approved dependency paths, health and freshness outcomes, representative capacity, host/SKU/scale, cost, and rollback. For GloFAS, prove the Snowflake staging/metadata-to-Blob-to-authenticated-API handoff if that path is in scope; otherwise record it as excluded. Keep data ownership in its existing component.
- **Operations evidence:** establish safe shared telemetry, component/data outcomes and freshness, monitoring-pipeline-loss alerts, named dashboard/notification/runbook owners, immutable image/source/config provenance, capacity/cost baselines, and tested restore/replay/rollback. Test logs with synthetic PII canaries. Before any public exposure, review exact routes/data/licensing, third-party map flows, accessibility, and low-bandwidth behavior using the linked [Observability Assessment](docs/project/observability-assessment.qmd) and [Publication Gates](docs/project/publication-gates.qmd).
- **Separate subscription-service lane:** after its own plan-approval gate, nonproduction Entra employee/B2B authentication, authorization/privacy/consent, accessible UI, deletion, recovery, and no-send tests may proceed independently or in parallel. This is not Stage A and does not collect real preferences or launch the production registry. Production registration remains after shadow and must pass the [service plan's separate gate](docs/project/alert-subscription-service-plan.qmd#stop-and-go-gates).
- **Exit evidence:** accountable owners accept the inventory and IaC decision; Stage A evidence; workload-specific source/host/capacity results; identity-denial and release-provenance checks; telemetry, alert, and runbook exercises; and cost/recovery results, with remaining blockers explicit. Exit means readiness for later Azure stages only—not public production, publication approval, recipient collection, delivery, or AWS.

Matomo is optional and is not a service-telemetry prerequisite or milestone blocker. Add a tracker only after its owner and privacy/legal reviewers approve purpose, consent, region, retention/access, safe event taxonomy, and URL/referrer/IP handling. After readiness, continue the consultation and product slices below, then preserve the existing shadow-before-production-registry order. Live delivery, AWS rehearsal, and regional expansion remain separate later gates.

## Active Slices

1. Implement deterministic Storm Episode and immutable link-event runtime without activating unqualified forecast identity.
2. Produce ProductDecision v2 and ProductFactSet v2 for official Warning/Alert and forecast-only Warning; fail closed for unsupported or review cases.
3. Add the one-way V1 adapter and checksummed cross-repository ProductFactSet handshake.
4. Add strict root consumption without re-running Orchestration policy.
5. Render the compatibility profile from semantic facts and prove Alert Parity against independently sourced expected facts or output.
6. Integrate composition and publication manifests with real output-content privacy enforcement.
7. Exercise the implemented non-normative [Alert Packaging Consultation Pack](docs/project/alert-packaging-consultation.qmd) as the synthetic-only Stage A proof in the readiness milestone, through the manual Azure Job with no Snowflake, registry/recipient, queue, provider, or delivery-ledger access.
8. Complete accountable consultation and record the packaging decision before adding concise email or technical-report profiles.

## Later Gated Product Slices

9. Add typed official warning-zone, rainfall, and surge facts only after source licensing, supported semantics, and manual-review behavior are approved. A shadow cohort may exclude unapproved hazard expansions; this is not a universal blocker for a bounded cohort that does not use them.
10. Add independently versioned content and lifecycle-policy releases only after their corresponding consultation and policy decisions, before activating dependent behavior. This does not block Storm Episode/link-event persistence or Stage B source-checkpoint/comparison state.

## Later Gated Azure Stages

11. Run a non-sending multi-Country-Office shadow pilot over finalized source-ready manifests, V2 policy/composition, historical replay, and independent expected evidence for an approved cohort.
12. Launch the Entra-authenticated subscription registry independently, after shadow and its own service gate, with no queue, provider, or send path.
13. Define and approve Delivery Authorization, Azure SQL delivery state, outbox/inbox, Service Bus, resolver, provider feedback, suppression, reconciliation, and cutover contracts before a controlled live-send pilot.
14. Expand through measured Country Office/product rings and SLO/residency-driven regional cells only after live-pilot and recovery gates pass.

Stage B may use optional Storage Queue/Event Grid work hints and Azure SQL comparison/checkpoint state for replay; these are not Service Bus delivery transport, outbox authority, or permission to send.

## Blocked Decisions

- Approve historical/provider evidence for forecast identity stability and non-reuse.
- Approve supported official warning-zone, rainfall, and storm-surge sources and manual-review behavior.
- Approve minimum self-contained email facts, information density, section order, email/report packaging, and audience or locale variants.
- Approve presentation differences among official Alert, official Warning, and forecast-only Warning while preserving supplied Product Decision and complete cumulative 144-hour 34 kt semantics.
- Approve whether a linked report is optional, its failure fallback, and the owner of any future secure hosting; attachments and delivery remain separate decisions.
- Approve lifecycle update, downgrade, closure, all-clear, and regional-composition policy.
- Select delivery and attachment mechanisms only after focused reproducibility and provider review.
- Approve pilot Country Offices/recipients, Azure regions, data residency, delivery SLO/RTO/RPO, SQL/Service Bus operating model, provider/sending domains, and legacy retirement authority.

## Gates

All current slices through registration and the non-sending shadow remain non-sending. Stage B may use optional Storage Queue/Event Grid work hints and Azure SQL comparison/checkpoint state for replay; neither is delivery authority. The later controlled-send and global stages stay blocked until their explicit activation gates pass. Operational activation and external publication require the privacy, accessibility, certification, licensing, consultation, and accountable-approval checks in [Publication Gates](docs/project/publication-gates.qmd). Readiness contracts, integrity checks, self-checks, and rendered output do not satisfy those gates.

Hazard and lifecycle slices 9–10 apply when those features enter a pilot; unapproved hazards or lifecycle behaviors must be excluded from that cohort, but do not universally block a bounded shadow. Episode/link-event persistence and Stage B source checkpoints/comparison state remain distinct from delivery operational state.

The consultation pack is itself publication-sensitive review evidence. Exact synthetic assets require local/private screening before they are pushed to a public branch and accountable review before merge or broad cross-link promotion. A merged pack or stakeholder feedback does not approve a normative profile; that requires an accepted durable decision.

## Milestone History

- Established the root Portable Report Flow, safe baseline export, Snapshot Output Bundles, report comparison, and static publication.
- Added decision-driven portable alert rendering, deterministic facts and visuals, and Presentation Self-Checks independent of expected HTML.
- Implemented credential-free dry-run policy components while suppressing delivery and withholding operational persistence.
- Froze V1 behavior and completed V2 contract/canonicalization readiness with independent producer-consumer verification.
