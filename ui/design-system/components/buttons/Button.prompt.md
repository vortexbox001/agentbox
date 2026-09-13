Button is the primary interactive control for actions, submissions, and triggers.

```jsx
<Button intent="primary" onClick={handleSave}>Save Agent</Button>
<Button outlined>Cancel</Button>
<Button intent="danger" outlined>Delete</Button>
<Button disabled>Unavailable</Button>
```

**Variants:** `intent` sets the color (primary=navy fill, danger=red, success=green, warning=yellow). `outlined` renders border-only. Default (no intent) renders a subtle outlined button with border.

**Sizing:** Single size (14px text, 6px 12px padding, 8px radius) matching Dagster's button spec.
