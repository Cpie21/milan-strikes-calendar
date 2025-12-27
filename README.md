# Milan transport strikes → auto-updating Apple Calendar subscription (EN+ZH)

This template converts the Italian Ministry of Transport (MIT) **transport strikes RSS** into a single `.ics` file you can **subscribe** to in Apple Calendar.

What it targets:
- **Any strike that may affect Milan (Milano / Lombardy area)**
- Plus **national** transport strikes for key modes (local public transport / rail / air / highways)
- Event titles + descriptions are **English + Chinese only** (no Italian shown)

## Quick setup (GitHub Pages)
1) Create a **public** GitHub repo (e.g. `milan-strikes-calendar`)
2) Upload this whole folder into the repo (keep the same structure)
3) Enable GitHub Pages:
   - Repo → Settings → Pages
   - Source: Deploy from a branch
   - Branch: `main`, Folder: `/docs`

Your calendar URL will be:
`https://<YOUR_GITHUB_USERNAME>.github.io/<REPO_NAME>/milan-strikes.ics`

## Subscribe in Apple Calendar
- macOS: Calendar → File → New Calendar Subscription… → paste URL
- iPhone/iPad: Settings → Calendar → Accounts → Add Account → Other → Add Subscribed Calendar → paste URL

## Tuning (optional)
Edit `.github/workflows/update.yml`:
- `GEO_KEYWORDS`: add/remove cities/airports
- `INCLUDE_NATIONAL`: set to "0" if you only want explicit Milan/Lombardy mentions
- `NATIONAL_MODES`: expand to catch more national actions

## Notes
- Events are generated as **all-day** to avoid wrong time windows (strike times change frequently).
- Always verify details close to the date via official notices.
