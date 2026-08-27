---
name: testhub-admin-ui-design
description: Use when designing, reviewing, or refactoring TestHub Demo frontend admin UI in frontend/src, especially Vue 3 + Element Plus pages for requirements, configuration, tables, filters, side navigation, status displays, dialogs, and high-frequency backend management workflows. Apply the established dense, restrained, work-focused UI rules without changing APIs, routes, or business logic unless explicitly requested.
---

# TestHub Admin UI Design

## Purpose

Apply the local TestHub Demo admin interface standard. This is for long-running, high-frequency backend management screens, not marketing pages or visual experiments.

## Required Workflow

1. Inspect the target Vue page and nearby pages before editing.
2. Preserve existing API calls, router paths, stores, polling, pagination, dialog save/delete flows, and backend contracts unless the user explicitly asks for logic changes.
3. Use the current Vue 3 + Element Plus structure. Prefer scoped CSS and local template changes over new dependencies.
4. Read `references/admin-ui-rules.md` before substantial UI changes or reviews.
5. Validate frontend changes with `cd frontend && npm run build`.

## Design Direction

Default to a dense, restrained admin system:

- Compact page headers and data-first section panels.
- Clear workflow order for operational pages.
- High-density tables with stable row height and subtle borders.
- One primary action color; semantic color only for state.
- Icon buttons in table action columns when text would waste width or clip.
- Monospace for IDs, codes, task numbers, version numbers, and requirement numbers.

## Implementation Boundaries

Do not change:

- API wrapper functions or endpoint URLs.
- Vue router definitions.
- Backend models, serializers, views, or tasks.
- Existing loading, polling, pagination, selection, save, delete, upload, or generation behavior.

Allowed by default:

- Reorder page sections in the template for clearer workflow.
- Add display-only computed/helper functions for CSS classes or labels.
- Add scoped CSS classes for tables, action cells, panels, badges, and responsive behavior.
- Adjust Element Plus table column widths, `show-overflow-tooltip`, alignment, and fixed columns.

## Reference

For concrete page patterns, table rules, action column rules, navigation behavior, and CSS values, read:

- `references/admin-ui-rules.md`
