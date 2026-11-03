# CLAUDE.md

Guidance for Claude Code sessions working in this repository.

## Layout and commands

- `ec_analysis/` is the library (pure aggregation in `ec.py` / `other_clearances.py`, network edge in
  `parivesh.py`, constants in `config.py`); `scripts/*.py` are thin CLIs over it. Keep I/O at the edges.
- `python3 scripts/refresh_ec.py [--from DUMP] [--data-dir DIR]`, `python3 scripts/build_page.py [--out X]`,
  `python3 scripts/refresh_other_clearances.py [--from-dir DIR]`, `python3 scripts/build_other_clearances.py`.
- Verify with `pytest -q` and `ruff check .` (both offline). Never hit the PARIVESH API from tests; the
  golden fixtures in `tests/fixtures/` define the expected output bytes.
- `data/` and `docs/` are generated outputs tracked in git; do not hand-edit them.

<!-- source-fetch-toolkit:v1 (managed by ~/bin/add_source_fetch_section.py — edit there, not here) -->
## Source fetching for data collection & literature surveys

When a task needs a primary document (statute, regulator data, government release, paper, filing),
fetch the document itself — never cite a search snippet as if it had been read.

- **On the owner's Mac:** `fetch_source.py "<url | doi:… | celex:… | arxiv:…>" --out ./sources`
  (in `~/bin`; full guide `~/bin/SOURCE_FETCH_TOOLKIT.md`). Scheduled/unattended runs use only
  `bash /Users/umashankar/bin/fetch_source.sh "<target>"` (allowlisted) and then Read the `.txt` it reports.
- **Elsewhere (cloud sessions, CI):** follow the same ladder by hand — direct GET with a browser User-Agent →
  headless browser only if the page needs JavaScript → official alternates (DOI → OpenAlex
  `api.openalex.org/works/doi:<doi>` locations → repository copy; EUR-Lex → EU Publications Office
  `publications.europa.eu/resource/celex/<CELEX>`; arXiv pdf/abs) → Wayback Machine `id_` snapshot.
- **Hard rule:** a CAPTCHA, robot check, Cloudflare/Akamai/WAF challenge or login wall means stop on that
  host. Do not bypass it (no TLS impersonation, stealth browsers, identity rotation or challenge solving);
  look for the same document via another route, or report it as unavailable.
- **Record** for every figure: URL read, title/date, page/table, fetch route; mark abstract-only or
  snippet-only sources. Fetch politely (~1 request/second per host, no bulk crawling).
<!-- /source-fetch-toolkit -->
