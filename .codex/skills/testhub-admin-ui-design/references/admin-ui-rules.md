# TestHub Demo Admin UI Rules

## Product Context

The human using these pages is a tester, QA lead, or developer operating a backend management system repeatedly during the day. They need to scan records, filter, edit, delete, upload, generate, and inspect failures quickly. The UI should feel like a precise workbench: quiet, dense, predictable, and resilient on narrower app-browser viewports.

## Page Structure

Use this baseline for CRUD/list pages:

```text
page
  page-head
    eyebrow/module label
    h1
    short description
    global context control, usually project select

  data-section or workbench-panel
    section-head
      h2
      count/context line
      toolbar actions and filters
    dense-table
    pagination-bar
```

Use `workbench-panel` for operational flows such as test case generation, where the user must follow a sequence. Use `data-section` for ordinary list management.

## Information Hierarchy

- Page title: `24px`, weight `650`, one line when possible.
- Section title: `17px`, weight `650`.
- Body/help text: `14px`, muted, line-height around `1.6`.
- Eyebrow/module label: `12px`, muted, not bright blue unless it is an active state.
- Keep page header compact. Do not use marketing-style hero sections.
- Every table section should expose record count where available.

## Layout And Spacing

- Use an 8px spacing basis.
- Page content width: `width: min(1440px, 100%)`.
- Section/panel border: `1px solid #e6ebf2`; radius `8px`; white background.
- Section header padding: `12px 14px`.
- Toolbar gap: `8px`.
- Table cell padding: `8px 0`.
- Avoid large blank areas above tables. Back office pages should prioritize scan density.

## Tables

Use dense tables for high-frequency pages:

```css
.dense-table {
  --el-table-border-color: #edf1f6;
  --el-table-header-bg-color: #fbfcfe;
  --el-table-header-text-color: #6b7280;
  --el-table-row-hover-bg-color: #f8fbff;
  font-size: 14px;
}

.dense-table :deep(.el-table__header th) {
  height: 42px;
  padding: 0;
  font-weight: 650;
}

.dense-table :deep(.el-table__cell) {
  padding: 8px 0;
}
```

Guidelines:

- Avoid `border` prop on Element Plus tables when using the dense style; rely on subtle table tokens.
- Use `show-overflow-tooltip` for long titles, descriptions, URLs, prompts, steps, and expected results.
- Align numeric counts right when they are used for comparison.
- Use fixed right action columns only when the table can overflow horizontally.
- Keep row height stable; do not put multi-line buttons or large tags inside rows.

## Table Action Columns

Action columns must not clip in narrow viewports.

Default rule:

- Use icon buttons in table rows.
- Hide button text inside `.action-cell`.
- Keep each button `28px x 28px`.
- Use `align="center"` on operation columns.
- Widths:
  - 2 actions: `92px`
  - 3 actions: `128px`
  - 4 actions: `160px`

Use this pattern:

```vue
<el-table-column label="操作" width="92" fixed="right" align="center">
  <template #default="{ row }">
    <div class="action-cell">
      <el-button text type="primary" :icon="Edit" @click="openDialog(row)">编辑</el-button>
      <el-button text type="danger" :icon="Delete" @click="removeRow(row)">删除</el-button>
    </div>
  </template>
</el-table-column>
```

```css
.action-cell {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  white-space: nowrap;
}

.action-cell :deep(.el-button) {
  width: 28px;
  height: 28px;
  margin-left: 0;
  padding: 0;
  border-radius: 6px;
  font-weight: 600;
}

.action-cell :deep(.el-button span) {
  display: none;
}

.action-cell :deep(.el-icon + span) {
  margin-left: 0;
}
```

If text labels are necessary, increase the column width and verify in the app-browser viewport. Do not let action text wrap.

## Status And Badges

Use color only for meaning:

- Success/active/completed: green.
- Failed/destructive/error: red.
- Running/processing/current: blue.
- Inactive/archived/unknown: gray.
- Default/special marker: amber.

Use pill-style badges:

```css
.status-pill,
.text-badge {
  display: inline-flex;
  align-items: center;
  height: 22px;
  padding: 0 8px;
  border-radius: 999px;
  font-size: 12px;
  white-space: nowrap;
}
```

Do not color whole rows for state. Put state in the status cell and important counts/errors.

## Typography For Identifiers

Use monospace for:

- `REQ-001`, `TC-014`, version numbers, task numbers.
- Project codes, model names, API keys when displayed masked.
- Counts and percentages where column alignment matters.

Pattern:

```css
.mono-code {
  color: #374151;
  font-family: "SFMono-Regular", Consolas, "Liberation Mono", monospace;
  font-size: 13px;
  font-variant-numeric: tabular-nums;
}
```

## Filters And Toolbars

- Put list filters in the section header or directly below it.
- Search input first, then categorical filters, then refresh or create actions.
- For project-scoped requirement pages, keep project select in the page header as global context.
- Reset pagination to page 1 when filters change.
- Do not show disabled fake filters unless backed by current API behavior.

## Operational Workflows

For pages like `TestCaseManagement.vue`, show the work sequence explicitly:

```text
生成控制台
  version select
  requirement search
  selected count
  primary generate action
待生成需求表
生成任务表 with status, progress, success/failure counts, error summary
用例库 with search and pagination
```

Keep task feedback immediately below the action that created the task. Failed status needs an error summary and expandable details where available.

## Navigation

The app layout may use a draggable sidebar:

- Width range: `188px` to `320px`.
- Persist width in `localStorage`.
- Hide drag handle on mobile/narrow layout.
- Use a subtle resize affordance, not a heavy visual control.

Active menu state should be obvious through active color and local background. Side navigation should not use strong decorative color blocks.

## Responsive Rules

The in-app browser can be narrow. Verify at roughly 657px viewport width when fixing visible issues.

- Stack page header, section header, toolbar, and filters vertically below tablet width.
- Do not allow action columns to wrap or clip.
- Prefer icon-only table actions over text buttons on dense tables.
- Use `show-overflow-tooltip` instead of expanding row height for long content.

## Verification Checklist

Before finishing UI work:

- Run `cd frontend && npm run build`.
- Confirm no API, route, store, backend, or business logic was changed unless requested.
- Check operation columns on narrow viewport.
- Check left navigation width if layout changed.
- Check empty/loading/error states were not removed.
- Run `git diff --check`.
