RunStatusTag is a run's status pill: a colored dot plus label. started/running render neutral gray (not green/red). Pass a relative time as the label for run tables.
```jsx
<RunStatusTag status="success" label="2 hours ago" />
<RunStatusTag status="started" label="running now" />
<RunStatusTag status="failure" label="5 days ago" />
```
