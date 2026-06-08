---
name: a11y-web-scan
description: Plan and run accessibility scans for user-facing web outputs. Use when reviewing frontend UI, Quarto sites, generated HTML, or documentation sites before design polish or release.
---

# A11y Web Scan

Use this skill to make accessibility scanning part of the design process.

## Workflow

1. Identify user-facing pages, routes, or generated HTML outputs.
2. Prefer scanning rendered pages, not only source files.
3. Use available project tooling first: Playwright with `@axe-core/playwright`, Pa11y, axe-core, Lighthouse, or browser/MCP automation.
4. Run at least one automated scan for WCAG A/AA issues.
5. Recheck browser-only or manual-review findings in a real browser when possible, especially `color-contrast`.
6. Manually inspect keyboard navigation, focus order, visible focus states, labels, headings, landmarks, color contrast, zoom/reflow, alt text, and form errors.
7. Record known issues, suppressions, and follow-up work in project docs or issues.

## Report Shape

Keep accessibility results short and remediation-oriented. Prefer summaries like:

```markdown
# Accessibility Scan

- Generated: <timestamp>
- Scope: <pages/routes/files>
- Pages assessed: <count>
- Standard: WCAG A/AA where applicable

## Results

### `<page-or-route>`
- Pages/items: <before> -> <after> when comparing outputs
- `image-alt`: <before> -> <after>
- `heading-order`: <before> -> <after>
- `landmark-one-main`: <before> -> <after>
- `color-contrast`: <browser count>
- Top violations: `rule:count`, `rule:count`
- Manual-review queue: <remaining> remaining, <resolved> resolved, <confirmed> confirmed issues
- Next remediation: <one or two concrete fixes>
```

When comparing generated outputs, report rule count deltas instead of dumping raw violations. When rechecking incomplete/manual-review items, separate:

- confirmed issues
- resolved incomplete items
- residual manual-review items

This makes the output useful for prioritization instead of just being a long scanner log.

## Common Rule Focus

For design and generated-document workflows, prioritize rules that indicate systematic template problems:

- `image-alt`
- `heading-order`
- `landmark-one-main`
- `region`
- `page-has-heading-one`
- `color-contrast`
- form labels and accessible names

## Suggested Commands

Pa11y:

```bash
pa11y http://localhost:3000 --runner axe --reporter json
```

Lighthouse:

```bash
lighthouse http://localhost:3000 --only-categories=accessibility
```

Playwright + axe:

```typescript
import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

test('page has no automatically detectable a11y issues', async ({ page }) => {
  await page.goto('/');
  const results = await new AxeBuilder({ page })
    .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'])
    .analyze();
  expect(results.violations).toEqual([]);
});
```

## Rules

- Automated scans do not prove full accessibility compliance.
- Prefer fixing issues over suppressing them.
- Keep suppressions narrow and documented.
- Do not ignore keyboard and focus behavior just because automated scans pass.
- Include mobile/responsive states when the output is user-facing.
- Treat broad regressions in generated templates as higher priority than one-off content issues.
