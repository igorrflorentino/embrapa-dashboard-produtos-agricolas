# Security Policy

## Supported Versions

| Version | Support |
|---|---|
| 0.1.x | ✅ Actively supported |

---

## Reporting Vulnerabilities

If you discover a security vulnerability in this project, **do not open a public issue**.

### Private channel

Send an email to: **igorlopesc@gmail.com**

<!-- Alternative: if the repository has GitHub Security Advisories enabled:
Use GitHub's [Security Advisories](https://github.com/igorrflorentino/embrapa-dashboard-commodities/security/advisories/new) feature to report privately.
-->

### What to include in the report

- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Affected version
- Suggested fix (if any)

### Response time

| Stage | Deadline |
|---|---|
| Acknowledgment of receipt | 48 hours |
| Initial assessment | 7 days |
| Fix (if confirmed) | 30 days |

Critical vulnerabilities affecting production data will be prioritized.

---

## Project Security Practices

A summary of the implemented practices. Full technical details in [`ARCHITECTURE.md` → Security and Authentication](ARCHITECTURE.md#security-and-authentication) and [`docs/iam_setup.md`](docs/iam_setup.md).

- **Authentication**: Service Account Impersonation (OAuth 2.0) — no distributed JSON keyfile. Details in [`docs/auth_architecture.md`](docs/auth_architecture.md).
- **Credential protection**: gitleaks in pre-commit, a comprehensive `.gitignore`, sensitive variables filtered out of the logs.
- **Infrastructure**: Cloud Run with mandatory IAM, 4 Service Accounts with minimal roles, budget alerts.
- **Dependencies**: deterministic lockfile (`uv.lock`), `--frozen` in CI, dev/runtime separation.

---

## Scope

This policy covers:
- The source code in this repository
- The GCP infrastructure configurations described in the documentation
- The CI/CD workflows (GitHub Actions)

**Out of scope:**
- Vulnerabilities in upstream dependencies (report to the upstream project)
- Vulnerabilities in the GCP services themselves (report to Google)
- Configurations specific to individual developer environments

---

## Acknowledgments

We thank everyone who helps keep this project secure. Contributors who report valid vulnerabilities will be acknowledged (with permission) in the CHANGELOG.
