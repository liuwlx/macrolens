# Data Sources and Mapping Policy

The machine-readable registry is `database/seed/source_registry.json`. It contains canonical codes, provider candidates, source locators, mapping status and license flags.

## Official providers

| Provider | Use |
|---|---|
| BEA | PCE, detailed PCE components, GDP, income and spending |
| BLS | CPI, PPI, payrolls, unemployment, wages, JOLTS and ECI |
| Census | retail, durable goods, housing, construction, manufacturing and trade |
| Federal Reserve | FOMC documents, H.4.1, H.8, G.17, G.19 and Z.1 |
| New York Fed | EFFR, SOFR, OBFR and repo operations |
| US Treasury | nominal and real Treasury yield curves |
| FRED / ALFRED | unified discovery, secondary series and vintages when permitted |
| EIA | energy prices, inventories and production |
| DOL | unemployment insurance claims |

## Mapping states

- `verified`: adapter may ingest automatically;
- `pending`: metadata discovery or human review is required;
- `disabled`: source is not allowed to run;
- `license_required`: code exists, but public display remains disabled until the contract is recorded.

## Canonical-series rules

- External IDs are never primary keys.
- One canonical indicator may have multiple source mappings, but only one primary mapping at a time.
- Derived measures such as payroll change, year-over-year growth or annualized momentum have a formula definition and dependencies.
- An official unit, frequency or seasonal-adjustment change is a metadata change requiring review, not an ordinary value update.
- PCE contribution and chain-index calculations may not be approximated as production values unless clearly labeled and formula-versioned.

## First production onboarding order

1. FRED low-risk public series;
2. BLS CPI and labor series;
3. BEA PCE/GDP metadata mapping;
4. Treasury and New York Fed market rates;
5. Census and EIA;
6. official release calendars and FOMC documents;
7. licensed forecasts and market data only after legal approval.
