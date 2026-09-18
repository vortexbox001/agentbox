CheckRow surfaces one recorded check in the Agents-overview mark language: a pass/warn/fail-blocking/
not-run mark + icon, the check name, a one-line detail, and a right-aligned recorded time. It reuses
the existing `ax-result` mark and CHECK_META vocabulary, so it never introduces a new check type.
```jsx
<CheckRow status="pass" name="freshness" detail="materialized within 24h" recorded="Sep 18, 1:15 PM" />
```
