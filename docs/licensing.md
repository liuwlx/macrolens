# Licensing and Redistribution Controls

MacroLens treats source accessibility and redistribution permission as separate facts.

`source.license_policy` controls:

- `display_allowed`;
- `download_allowed`;
- `api_redistribution_allowed`;
- `ai_context_allowed`;
- `ai_training_allowed`;
- required attribution and restrictions.

Rules:

1. a series is not public merely because an API endpoint can return it;
2. commercial forecasts, CME probabilities, equity indices and credit-spread series remain disabled until rights are recorded;
3. restricted values must be omitted—not blurred or merely hidden in CSS—from API responses;
4. export and AI context each require their own permission;
5. policy changes are versioned and audited;
6. legal review records the contract, territories, products, users and expiration date outside the source code.
