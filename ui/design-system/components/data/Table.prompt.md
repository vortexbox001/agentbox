Table is a grid-based data table. Pass `fullBleed` for object-overview / list pages (the Dagster Runs pattern) — horizontal rules edge to edge, a 2px header rule, per-column vertical dividers, and the first/last cells inset 24px so content lines up with surrounding copy. Omit it for detail pages (single object): inset content, hairline rules, no vertical dividers. To bleed past a padded card, give the table a negative side margin equal to the card padding (e.g. `margin: 0 -24px`).
```jsx
<Table fullBleed columns={[
  { key: 'name', label: 'Agent', width: 'minmax(0,2fr)' },
  { key: 'status', label: 'Status', width: '1fr', render: r => <RunStatusTag status={r.status} label={r.last} /> },
  { key: 'runs', label: 'Runs', width: '80px' },
]} rows={agents} onRowClick={openAgent} />
```
