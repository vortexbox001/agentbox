Summary renders the agent's final message as the safe markdown subset from `render_summary`:
`##`/`###` headings as small uppercase labels, bold, inline-code chips, bullet lists, and links —
never raw markup. When no message exists it shows the foot-line fallback.
```jsx
<Summary html={renderedSummaryHtml} />
<Summary fallback="ok · 3 turns · 0 files written" />
```
