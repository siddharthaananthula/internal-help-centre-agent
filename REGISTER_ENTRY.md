# Agent register entry

| Name | Owner | Users | Data access | Tools | Status | Monthly cost estimate |
|---|---|---|---|---|---|---|
| Superloop Internal Help Agent | Siddhartha Ananthula | Frontline support staff (internal) | 38 public help articles (read-only, allow-listed); synthetic account records only (app-controlled verification) | `search_help`, `get_article`, `lookup_service_status` (all read-only, MCP) | Prototype | About USD 0.22 per month |

**Cost assumption:** 1,000 answers per month × measured agent cost of USD 0.000219 per answer (mean of 3 eval runs, `eval/results/final_summary.json`, gpt-4o-mini list prices). It excludes query embeddings, evaluation and judge calls, hosting and staff time. At 10,000 answers per month the same rate gives about USD 2.19.
