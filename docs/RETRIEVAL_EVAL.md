# Semantic Retrieval Evaluation & Benchmark Report

**Embedding Model:** `BAAI/bge-small-en-v1.5` (Cosine Space)
**Evaluation Date:** 2026-11-01
**Total Benchmark Queries:** 10

## Overall Performance Summary

- **Recall@5:** `100.0%` (10/10)
- **Mean Reciprocal Rank (MRR):** `1.0000`

## Per-Query Retrieval Breakdown

| # | Domain / Query | Expected Proposal | Actual Rank | Reciprocal Rank | Top Retrieved Chunks |
| :--- | :--- | :--- | :---: | :---: | :--- |
| 1 | **Healthcare Intake Modernisation**<br>_reduce patient readmission rates in hospital network and digital intake_ | `proposal_healthcare` | **1** | 1.0 | proposal_healthcare (0.74), proposal_healthcare (0.68), proposal_healthcare (0.68) |
| 2 | **Fintech Automated Reconciliation**<br>_core banking migration, financial audit, and automated reconciliation_ | `proposal_fintech` | **1** | 1.0 | proposal_fintech (0.72), proposal_fintech (0.71), proposal_fintech (0.69) |
| 3 | **Retail POS & Shopify Inventory**<br>_increase ecommerce conversion and synchronize pos inventory with shopify_ | `proposal_retail` | **1** | 1.0 | proposal_retail (0.84), proposal_retail2 (0.76), proposal_retail (0.75) |
| 4 | **Manufacturing Floor Monitoring**<br>_predictive maintenance and sensor alerts for factory floor equipment_ | `proposal_manufacturing` | **1** | 1.0 | proposal_manufacturing (0.77), proposal_manufacturing (0.75), proposal_manufacturing (0.74) |
| 5 | **Fleet & Delivery Operations**<br>_optimise last-mile delivery routing, driver dispatch, and fleet utilisation_ | `proposal_fleet` | **1** | 1.0 | proposal_fleet (0.80), proposal_fleet (0.76), proposal_fleet (0.76) |
| 6 | **Supply Chain & Logistics Visibility**<br>_multi-hub supply chain visibility and inventory platform across hubs_ | `proposal_logistics` | **1** | 1.0 | proposal_logistics (0.86), proposal_logistics (0.81), proposal_logistics (0.75) |
| 7 | **Construction Field Operations**<br>_field operations management, safety compliance, and daily job site reporting_ | `proposal_construction` | **1** | 1.0 | proposal_construction (0.76), proposal_construction (0.71), proposal_consulting (0.68) |
| 8 | **Consulting Resource Management**<br>_professional services project tracking, consultant timesheets, and resource utilization_ | `proposal_consulting` | **1** | 1.0 | proposal_consulting (0.76), proposal_construction (0.75), proposal_consulting (0.75) |
| 9 | **Food Distribution & Cold Storage**<br>_cold storage warehouse operations, pallet racking, and food distribution platform_ | `proposal_distribution` | **1** | 1.0 | proposal_distribution (0.74), proposal_distribution (0.72), proposal_logistics (0.70) |
| 10 | **Multi-Channel Retail Analytics**<br>_multi-channel inventory synchronisation, stock reconciliation, and retail analytics_ | `proposal_retail2` | **1** | 1.0 | proposal_retail2 (0.83), proposal_retail2 (0.80), proposal_retail (0.80) |

## Analysis & Tuning Takeaways

1. **Heading-Aware Indexing:** Prefixing chunk text with `## <Heading>` sharply increases semantic alignment for domain-specific queries.
2. **Cosine Normalization:** Dense normalized representations allow clear discrimination across closely related operational domains (e.g. logistics vs fleet vs distribution).
3. **Fallback Ladder:** Exact industry filtering achieves 1.0 MRR on matched industries, while unfiltered semantic search provides resilient backoff.
