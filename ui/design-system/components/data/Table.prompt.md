Table is a grid-based data table.
```jsx
<Table
  columns={[{ key: 'name', label: 'Name' }, { key: 'status', label: 'Status', render: r => <Badge label={r.status} intent={r.status} /> }]}
  rows={[{ name: 'summarizer', status: 'running' }]}
/>
```
