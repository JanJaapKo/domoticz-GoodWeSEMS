# Contributing

Bug reports and feature proposals are welcome through GitHub Issues. For code changes, keep each pull request focused and include tests for changed behavior.

## Run Checks Locally

The regression workflow runs on Python 3.11 and 3.13. Install the test dependencies, then run the same checks locally:

```bash
python -m pip install requests coverage
python -m coverage run --source=. plugin_test.py
python -m coverage report --fail-under=80 -m GoodWe.py plugin.py exceptions.py
python manual_test.py
python -m compileall -q GoodWe.py plugin.py exceptions.py fakeDomoticz.py
```

`plugin_test.py` exercises the GoodWe API models and mocked request contracts. `manual_test.py` uses a fake Domoticz host to exercise plugin device updates and station discovery. Neither suite needs GoodWe credentials or a live SEMS account.

## Regression Test Guidelines

- Add or update a regression test whenever a bug is fixed or observable behavior changes. First reproduce the failure in a test where practical.
- Verify station discovery and telemetry use the SEMS+ endpoints only. Assert that login failure and polling do not call retired legacy login, station-list, monitor, or control endpoints.
- For API changes, test request URL, payload, headers, regional host selection, and error responses with mocked HTTP calls. Cover incomplete or empty telemetry where it affects Domoticz-facing data.
- For plugin changes, use the fake Domoticz host to cover station discovery and persistence, missing station IDs, device creation/update behavior, heartbeat scheduling, and protection against suspicious zero energy-counter resets when relevant.
- Keep tests deterministic and offline. Mock network calls; do not commit credentials, account data, or live-service dependencies.
- Keep plugin-facing station and inverter data safe for incomplete API responses. The plugin supports SEMS+ only; do not add legacy SEMS endpoint fallbacks.
- Update the README or plugin configuration documentation when user-visible behavior, setup, or limitations change. Update the plugin version for a release as appropriate.

## Pull Requests

Describe the user-visible change and any compatibility implications. Include the regression scenarios covered, and confirm the local checks above pass before requesting review.

## Versioning

- Bump the minor version when creating a new feature branch.
- Bump the major version when explicitly requested, or when a mandatory plugin configuration attribute is added or removed.
- Use the patch version for other release fixes that do not require a major or minor bump.