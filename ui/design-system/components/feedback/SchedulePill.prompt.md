SchedulePill shows an agent's automation: a clock (schedule) or sensor icon, the frequency in plain English, and an inline enable toggle.
```jsx
<SchedulePill type="schedule" label="Every day at 7:00 AM" on onToggle={fn} />
<SchedulePill type="sensor" label="Every Monday at 6:00 AM" on onToggle={fn} />
```
