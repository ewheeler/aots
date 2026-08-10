# Separate Alert Classification From Country Threat

Status: Accepted for dry-run implementation; operational sending remains disabled pending provider and stakeholder approval.

Warning and Alert are country-level products. A Country Office first qualifies through a versioned forecast threat assessment. A separate authoritative current storm state then determines the product type:

- A qualifying threat with a fresh official status below hurricane strength produces a Warning.
- A qualifying threat with a fresh official hurricane status produces an Alert.
- Missing, stale, conflicting, or unsupported official status produces manual review rather than an inferred product.
- A non-qualifying or ineligible country produces no product.

Global official hurricane status controls the product type even when the local forecast contains only tropical-storm-force winds. Product content must state the official classification and local hazard separately.

## Decision Gate

- Providers are configured explicitly for the dry-run contract. Atlantic and Eastern Pacific use NOAA/NHC (RSMC Miami); Central Pacific uses NOAA/CPHC (RSMC Honolulu). South Atlantic, the LACRO-adjacent Southeast Pacific area whose regional responsibility boundary is not yet validated, and unmapped basins require manual review. No provider is inferred from ECMWF output.
- NHC/CPHC public-advisory RSS feeds are the proposed dry-run transport for configured basins. Public advisories are issued on a nominal six-hour cadence, so the initial freshness limit is nine hours. Provider/stakeholder approval, live retrieval, source authentication, and Snowflake external-network configuration remain deployment gates.
- NHC/CPHC status normalization supports hurricane, tropical storm, and tropical depression classifications. Potential, subtropical, post-tropical, malformed, or unknown classifications require manual review rather than being treated as below-hurricane Warning status.
- Provider adapters normalize storm identity, status, advisory identity, observation time, freshness, conflicts, sustained wind, units, and averaging convention into `CurrentStormState`.
- A canonical storm episode ID reconciles advisory and forecast identities before classification.
- Eligible Country Offices come from a dedicated versioned registry, not general pipeline activation or recipient configuration.
- The initial threat predicate is versioned and evaluated upstream. It must state threshold, probability, population and tile requirements, 144-hour completeness, and incomplete-data behavior. The classifier accepts its result and does not reproduce those rules.
- The default forecast horizon is 144 hours. Exceptions require an explicit contract version.
- The first product may use validated cumulative 144-hour exposure. Period-indexed impacts remain unavailable until stakeholders require them and upstream producers provide them.
- Forecast-conditioned PiN/CHiN must not be labeled current observed need. Forecast exposure must not be labeled observed affected population or damage.
- A lifecycle stream is one canonical storm episode plus Country Office. Product type is decision data, not lifecycle identity.
- Decision events and recipient delivery attempts are separate. Identical fact versions produce the same decision event; retries create separate delivery attempts.
- Warning-to-Alert escalation is allowed for the same forecast after an advisory update. Alert-to-Warning downgrade and all-clear remain manual until a later operational decision records automated behavior.
- Regional digests may aggregate delivery, but they do not collapse country decision identities.
- Rainfall and storm surge remain explicitly unavailable until validated upstream artifacts exist.
- No real or shadow email is sent without separate operational approval.

## Implementation Shape

The operational classifier is logically owned by Orchestration. It is one side-effect-free artifact with normalized primitive inputs and a versioned decision output. Snowflake adapters may load facts, call it, persist the decision, and deliver products, but must not duplicate classification rules.

The Portable Report Package consumes a versioned Alert Decision artifact containing current storm state, country threat assessment, hazard availability, and product decision. It renders and audits the supplied decision; it never infers Warning or Alert from 34kt, 50kt, or 64kt forecast values.

Expected Alert Email HTML is optional provenance-qualified reference evidence copied into the output bundle. It is not required to render local Warning or Alert output, and expected-output alert comparison remains future work.

## Authority Evidence

Verified 2026-08-07 against official NOAA/WMO-facing documentation:

- [Worldwide Tropical Cyclone Centers](https://www.nhc.noaa.gov/aboutrsmc.shtml) assigns Atlantic/Eastern Pacific to RSMC Miami and Central Pacific to RSMC Honolulu.
- [NHC/CPHC RSS Feeds](https://www.nhc.noaa.gov/aboutrss.shtml) documents the Atlantic, Eastern Pacific, and Central Pacific basin feeds used by the authority map.
- [NHC Tropical Cyclone Product Descriptions](https://www.nhc.noaa.gov/aboutnhcprod.shtml) states that public advisories contain a fixed-format current summary and are issued on a nominal six-hour cadence.
- [NHC Glossary: Maximum Sustained Surface Wind](https://www.nhc.noaa.gov/aboutgloss.shtml#MAXSUSTSURFWIND) defines tropical-cyclone intensity using the highest one-minute average wind at 10 metres with unobstructed exposure.

The reviewed WMO centre table does not list a South Atlantic tropical cyclone centre. For the LACRO-adjacent Southeast Pacific, the dry-run configuration deliberately avoids claiming that the whole Southeast Pacific lacks WMO coverage: it remains manual review until its exact boundary and warning responsibility are validated against the WMO South Pacific operational plan by the relevant regional meteorological owner.

## Consequences

- The dry-run authority map, exact-feed retrieval/parsing, normalized advisory adapter, and explicit storm-identity reconciliation are implemented locally. Provider/stakeholder approval, source-authentication policy, scheduled Snowflake network deployment, and production monitoring remain required before operational activation.
- Existing grouped Watch history cannot always prove country- or recipient-level delivery and must remain explicitly legacy evidence.
- The current 34kt and 50kt procedures cannot be fixed by naming changes alone.
- Credential-free tests can exercise classification and portable rendering with synthetic facts.
- Rainfall, surge, period impacts, automated downgrade, and all-clear remain independent future decisions.
