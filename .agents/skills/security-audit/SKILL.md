---
name: security-audit
description: Review code for security vulnerabilities, secret leaks, dependency CVEs, and authentication or authorization risks. Report findings only unless the user approves fixes.
---

# Security Audit

Use this skill for security reviews before shipping, after sensitive changes, or when auditing a module, PR, or full codebase.

## Rule

Report first. Do not fix anything without explicit approval.

## Workflow

1. Confirm scope: module/PR/full repo, target directory, language/framework, and review depth.
2. Scan for hardcoded secrets and sensitive data in source, config, CI, Dockerfiles, docs, and test fixtures.
3. Check dependency vulnerabilities with project-appropriate tools when available, such as `pip-audit`, `npm audit`, or package-manager audit commands. When the `setup-python-guardrails` skill has configured `bandit` and `pip-audit` as pre-commit hooks, run `pre-commit run bandit --all-files` and `pre-commit run pip-audit --all-files` for deterministic security checks.
4. Review OWASP-style risk categories: injection, authentication, sensitive data exposure, access control, misconfiguration, XSS, insecure deserialization, vulnerable dependencies, and logging/monitoring gaps.
5. Review authentication and authorization patterns: token validation, session handling, API keys, RBAC/ABAC checks, CORS, and protected routes.
6. Produce a prioritized findings report with file/line references and recommended remediation.

## Secret Scan Focus

Check for:

- API keys, tokens, private keys, JWTs, and credential JSON.
- Database URLs with embedded credentials.
- `.env*` files accidentally committed.
- Secrets in test fixtures, docs, and CI logs.
- Real customer, personal, or operational data.

## Severity

- Critical: active secret exposure, auth bypass, remote code execution, SQL injection, public sensitive data leak.
- High: exploitable access-control flaw, unsafe token handling, vulnerable dependency with practical exploit path.
- Medium: missing hardening, weak validation, risky logging, incomplete monitoring, stale dependency without confirmed exploit path.
- Low: hygiene or documentation gaps with limited direct exploitability.

## Report Shape

```markdown
# Security Audit: <scope>

## Summary
- Scope:
- Review depth:
- Overall rating: Excellent / Good / Needs Work / Critical

## Critical Findings
1. <finding> -- <file:line> -- <remediation>

## High Findings
1. <finding> -- <file:line> -- <remediation>

## Medium Findings
1. <finding> -- <file:line> -- <remediation>

## OWASP Review
- Injection:
- Authentication:
- Sensitive data exposure:
- Access control:
- Misconfiguration:
- XSS:
- Deserialization:
- Vulnerable dependencies:
- Logging and monitoring:

## Top 3 Priorities
1. <fix first>
2. <fix next>
3. <fix later>

## Recommendation
<ship / pause / do not ship until fixes>
```

## Rules

- Prioritize concrete evidence over generic checklist output.
- Include file and line references where possible.
- Separate confirmed findings from hypotheses.
- Do not paste secrets into the report; redact values and describe location.
- Ask before applying fixes.
