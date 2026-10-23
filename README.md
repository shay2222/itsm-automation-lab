# ITSM Automation Lab (ServiceNow)

A small project that turns GPU health-check output into ServiceNow incidents, with duplicate protection and a dry-run mode. It runs against a free ServiceNow Personal Developer Instance (PDI), a learning sandbox, not a production ITSM system.

## What it does

| File | Purpose |
|---|---|
| `snow_client.py` | Minimal Table API client (find and create). Reads credentials from environment variables. |
| `gpu_to_incident.py` | Reads a health-check JSON report and creates incidents for WARN and CRIT GPUs. |
| `sample/gpu_report.json` | Example report with one OK, one WARN, and one CRIT GPU. |
| `tests/test_gpu_to_incident.py` | Tests with a fake client. No account or network needed. |
| `notebooks/servicenow_demo.ipynb` | Colab notebook that runs the dry run and the live create against your PDI. |
| `.github/workflows/tests.yml` | Runs the tests on every push. |

## Rules the script follows

- **OK (or pass):** no action.
- **WARN:** incident with urgency 2 and impact 2.
- **CRIT (or fail):** incident with urgency 1 and impact 1.
- **Duplicates:** if an active incident already exists for the same host and GPU, the script reports its number and creates nothing.
- **Dry run:** shows what would happen and makes no changes.

The script reads reports from both health checkers in the portfolio, which use different status words.

## Run it

Tests (no account needed):

```bash
pip install -r requirements.txt
pytest -v
```

Against your PDI:

```bash
export SNOW_INSTANCE_URL=https://devXXXXX.service-now.com
export SNOW_USER=admin
export SNOW_PASSWORD=...        # never commit this
python3 gpu_to_incident.py sample/gpu_report.json --host lab-01 --dry-run
python3 gpu_to_incident.py sample/gpu_report.json --host lab-01
```

Or use the Colab notebook, which asks for the credentials with a hidden prompt.

## Security

- Credentials live in environment variables, Colab's hidden prompt, or GitHub repository secrets. They are never in the code.
- `.gitignore` excludes `.env` files.
- Use a PDI-only account, not a work account.

## Limits

- Targets a personal developer instance, not a production ServiceNow environment.
- Creates incidents only. It doesn't implement change approvals, assignment rules, or SLA handling.
- Dedup checks one query per GPU. It doesn't handle race conditions between two runs at the same moment.
- Tests use a fake client. The live path was exercised only against the PDI, and the screenshots show that run.
