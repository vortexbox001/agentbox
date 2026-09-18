Disclosure is a bordered card whose full-width header collapses the body. The header shows a
chevron reflecting state, the title, and a right-aligned muted closed-state note; it carries
`aria-expanded` and toggles on click or Enter/Space. Used for every run-detail section.
```jsx
<Disclosure id="summary" title="Summary" note="final message from the agent" open>
  <p>Rendered final message…</p>
</Disclosure>
```
