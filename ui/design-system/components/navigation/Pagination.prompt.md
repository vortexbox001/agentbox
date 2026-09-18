Pagination is a Prev · page-indicator · Next control for paging a list view. Prev is disabled
on the first page and Next on the last page (never a dead link); the current page lives in the
URL so a copied link restores the view.

```jsx
<Pagination page={2} pages={4} onChange={setPage} />
```

In the AgentBox app it is rendered by the shared `pagination(page, pages, base_query)` Jinja
macro, whose Prev/Next are real `?…&page=` links (works without JS) that `runs-list.js` may
enhance with `history` syncing.
