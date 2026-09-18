# Contract: GitHub Projects v2 GraphQL read

The outbound query `GitHubProjectsClient.fetch_board` issues each tick, its pagination, and how a
`BoardItem` is derived. Authority: `orchestrator/github_projects.py`. Projects v2 is only available in
the GraphQL API (`https://api.github.com/graphql`); the REST API does not expose it — this is the
spec's premise for a polling sensor (FR-003).

## §1 Request

- **Endpoint**: `POST https://api.github.com/graphql`.
- **Headers**: `Authorization: Bearer <GITHUB_PROJECT_TOKEN>` (§/orchestrator-model §6),
  `Content-Type: application/json`. The token needs board read scope (a classic PAT with
  `read:project` + repo read, or a fine-grained token with Projects: read + Contents/Issues: read).
- **Transport**: the already-pinned `httpx`, with a bounded timeout; a timeout is a transient error
  (skip-with-reason, FR-019).

## §2 Query

```graphql
query($owner: String!, $project: Int!, $after: String) {
  organization(login: $owner) {
    projectV2(number: $project) {
      title
      items(first: 100, after: $after) {
        pageInfo { hasNextPage endCursor }
        nodes {
          id                                            # the Projects v2 item id (BoardItem.item_id)
          fieldValues(first: 20) {
            nodes {
              ... on ProjectV2ItemFieldSingleSelectValue {
                name                                    # the Status OPTION name
                field { ... on ProjectV2SingleSelectField { name } }   # the FIELD name ("Status")
              }
            }
          }
          content {
            __typename                                  # Issue | PullRequest | DraftIssue
            ... on Issue {
              number title body url
              repository { nameWithOwner }
              labels(first: 50) { nodes { name } }
            }
          }
        }
      }
    }
  }
}
```

- **Owner fallback**: if `organization(login:)` resolves null (a user-owned board), retry the query
  with `user(login: $owner)` (spec Assumption "Board ownership"); this path may work but is not a
  requirement.
- **Status field**: the single-select field whose `field.name` equals `"Status"` (case-insensitively);
  its `name` is the item's current Status option. If no such field exists on the board, that is an
  `Unresolvable("Status field")` (FR-020).

## §3 Pagination (FR-021)

Loop over pages: start with `after: null`, and while `items.pageInfo.hasNextPage`, re-issue with
`after: items.pageInfo.endCursor`, accumulating `nodes`. All items across all pages are considered, so
an item beyond the first page still launches (US7 #3).

## §4 Deriving a `BoardItem` and filtering

For each node the client builds a `BoardItem` and keeps it only when it is a launch candidate:

| Step | Rule |
|------|------|
| Content type | Keep only `content.__typename == "Issue"`; drop PRs and drafts (FR-004). |
| Status match | Keep only when the item's Status option name equals the configured `status`, compared **case-insensitively**. If the configured `status` matches no option present anywhere on the board, raise `Unresolvable("status option '<status>'")` (FR-020). |
| `repo` filter | If configured, keep only when `repository.nameWithOwner` equals `repo`, compared case-insensitively (spec clarification). |
| `label` filter | If configured, keep only when the issue's `labels.nodes[].name` contains it. |
| Fields | `item_id=node.id`, `number`, `title`, `body`, `url`, `repo=nameWithOwner`, `labels`. |

The client returns the filtered list of issues-in-status; PRs, drafts, wrong-status, and filtered-out
items are already gone, so admission (`plan_tick`) never launches them and they never hold the slot
(FR-004 / US4 #3).

## §5 Error mapping (FR-019/FR-020)

| Condition | Raised | Sensor result |
|-----------|--------|---------------|
| HTTP 5xx, connection error, timeout | `BoardError` | skip "GitHub unavailable: …", cursor untouched (FR-019). |
| HTTP 403/429 or a GraphQL `RATE_LIMITED` error | `RateLimited` | skip "GitHub unavailable: rate limited", cursor untouched (FR-019). |
| `organization`/`user` null or `projectV2` null | `Unresolvable("board <owner>/<project>")` | skip naming the board (FR-020). |
| No `Status` single-select field on the board | `Unresolvable("Status field")` | skip naming the field (FR-020). |
| Configured `status` matches no option on the board | `Unresolvable("status option '<status>'")` | skip naming the option (FR-020). |

All are caught inside the sensor, so one agent's bad board never crashes the daemon or affects other
sensors (US7 #2 / US8). Redaction masks the token if it ever appears in an error string.

## §6 What the query never returns to a run

The token, the raw GraphQL response, and the board cursor stay in the daemon. Only the derived issue
fields (`number`, `repo`, `url`, `title`, `body`, `item_id`, `feature_key`) travel to a run, via the
tags + `run_config` handoff (orchestrator-model §4) — the body as a read-only file, never on the
command line or in an env value (FR-014/FR-017).
