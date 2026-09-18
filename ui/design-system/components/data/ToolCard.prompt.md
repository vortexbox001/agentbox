ToolCard renders one transcript tool invocation: a head line (name, ellipsised description,
right-aligned mono marker) over IN and OUT rows clamped to 3 lines with a token-background fade
and a "Show all N lines" link when overflowing. Diff OUT rows render expanded by default; a
failed/missing OUT reads in the failed/warning colour.
```jsx
<ToolCard name="Bash" description="npm test" marker="exit 1" in_text="npm test"
          out_text={longOutput} out_overflow out_lines={40} out_intent="failed" />
```
