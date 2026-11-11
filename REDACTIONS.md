# Redactions

The destination is a **public** GitHub repository. Live secrets were never
copied as-is. Originals on the box were not modified.

## Replacements made

| Export path | Kind | What was done |
|---|---|---|
| `nfl-props/.env` | Odds API key in an env file | **Not copied.** `nfl-props/.env.example` was written with `ODDS_API_KEY=REDACTED_ODDS_API_KEY`. |
| `nfl-props/data/secrets/odds_api_key` | Odds API key file | Placeholder file written containing only `REDACTED_ODDS_API_KEY`. |
| `nhl-sog/shadow/xlineup/raw/20261103_{1239,1307,1335,1436}/*.json` (22 files) | X API `meta.next_token` pagination cursors | Each `next_token` value replaced with `REDACTED_X_NEXT_TOKEN`. Tweet bodies and public author metadata were left intact. These are search pagination cursors, not account bearer tokens. |

No source file in the export contains a live key or a leftover placeholder inside code. Python clients already load the Odds API key from `ODDS_API_KEY`, then `nfl-props/data/secrets/odds_api_key`, then `.env`, and interpolate `apiKey={key()}` (or equivalent) into request URLs. Those interpolations were left intact so the code still runs if a reviewer supplies a key.

A first automated scrub used a URL regex that treated `{key()}`, `{K}`, `{fp.key()}`, and `os.environ["ODDS_API_KEY"]` as secret values and would have broken those files. Those copies were restored from the unmodified originals. `nfl-props/sidecars/oddsapi/oddsapi.py` was also restored after a similar false positive on `line.startswith("ODDS_API_KEY=")`.

gitleaks also flagged six ESPN boxscore `publishedkey` fields (public recap content ids) in `nhl-sog/audit/20261031_yinzer/cfb/espn/` and `prop-finder/data/cache/`. Those were left unchanged.

## Scanners

See the Secret scanning section of the top-level README for gitleaks and custom-scan results.
