**Intent.** Bring the Runs overview up to the standard of the Agents overview and Dagster's own Runs page: a tabbed header, a filter row, a table whose columns answer "what ran, against what, who launched it, how did it go, what did it cost", a status that is actually true, and a one-click path to the same run in Dagster. Alongside it, tidy the shell: Runs leads the left-hand navigation, Settings appears once, and the logo takes you home. This is presentation and read-path work only; no agent schema or run-record changes.

**What changes.**

*Runs overview page*
- **Correct run status (#163).** Every row currently shows `ok`. The list reads `status` from the harness's self-reported `report.json`, so a run that Dagster marked failed, timed out, or cancelled — or that is still queued or in progress — is misreported. Status must reflect the real outcome of the run as Dagster records it, with the report status as a fallback only when Dagster is unreachable (and marked as last-known). Status text and colours use the existing `run_status_tag` intents.
- **Tabbed header (#164).** The page gets the same tabbed header as the Agents overview, rendered with the shared `tabs` macro, with a count badge per tab. Tabs partition runs by state, following Dagster's Runs page: All, In progress, Succeeded, Failed. The tabs replace the current Status dropdown.
- **Filter row (#164).** Under the tabs, a filter control that looks and behaves like the one on the Agents overview (ghost Filter button that reveals a text filter), narrowing the table by agent, model, target, or run id. The existing agent and date-range filters remain available through it; filter state stays in the URL so a filtered view can be bookmarked.
- **Columns (#171, #165, #167).** The table's columns become, in order: **Run**, **Status**, **Agent**, **Model**, **Target**, **Launched by**, **Checks**, **Created**, **Duration**, **Cost**. The separate Date and Time columns and the Attempts column are removed.
  - *Target* is the run's target exactly as Dagster's Runs page lists it (the asset key or job name).
  - *Launched by* is what started the run: the schedule or sensor name, or a manual launch.
  - *Checks* shows the run's check results the same way the Checks column does on the Agents overview.
  - *Created* is a single timestamp formatted `Sep 17, 1:15 PM`, in the operator's local time; the full timestamp is available on hover.
  - *Duration* is elapsed run time; an in-progress run shows time so far.
  - *Cost* stays as today, with unknown cost shown as `—`, never as zero.
- **Link to the Dagster run (#166).** In the Run column, right-justified, a link icon in the indigo colour ramp opens that run in Dagster in a new tab. The run id itself still links to the AgentBox run page. When Dagster is not configured the icon is not rendered (consistent with #8).
- **Matching fonts (#170).** The Agent and Model cells use the same type treatment as the same two columns on the Agents overview (the mono style), so the two tables read as one system. The agent name links to that agent.
- **Pagination (#168).** The table shows 30 runs per page, newest first, with pagination controls below it. Tabs and filters apply before pagination, tab counts reflect the whole filtered set, and the current page is part of the URL.

*Shell and navigation*
- **Navigation order (#169).** The left-hand navigation lists **Runs** first, then a horizontal rule, then **Agents**.
- **One Settings entry (#169).** The Settings item in the primary navigation is removed. The only Settings entry is the one at the bottom of the navigation, which opens the settings modal; everything the separate Settings page offered is consolidated into that modal, and `/settings` no longer appears as a destination in the nav.
- **Logo links home (#14).** The logo and wordmark at the top of the navigation are a link to the home page, in both the expanded and collapsed navigation, with a visible keyboard focus state.

All of it follows the design system: tokens only, no inline styles, every control from the shared macros. Pagination is not yet in the macro set, so it lands in the design system first and as a shared macro second, then is used here.

**What I'd check.**
- Trigger one run that succeeds, one that fails, one that times out, and leave one in progress. Each row's Status matches what Dagster shows for that run, and each run appears under the right tab with correct tab counts.
- Stop Dagster: the page still loads from local run records, statuses are marked last-known, and no Dagster link icons are dead links.
- Compare the Runs and Agents overviews side by side in light and dark themes: same tab header, same filter control, same font in the Agent and Model columns.
- Target and Launched by match Dagster's Runs page for a scheduled run, a sensor-launched run, and a manual run.
- A run created at 13:15 on 17 September reads `Sep 17, 1:15 PM`. A run with unknown cost shows `—`.
- The Dagster icon opens the correct run in a new tab; the run id opens the AgentBox run page.
- With 31 or more runs, the first page shows 30 and the second the rest; changing tab or filter returns to page 1; a copied URL restores tab, filter, and page.
- The navigation reads Runs, rule, Agents; there is exactly one Settings entry and it opens the modal with every setting that used to be on the Settings page; the logo returns home from any page, including with the navigation collapsed.
- The UI test suite passes, including design-system conformance (no literal colours or pixel values, no inline styles, no hand-rolled controls).

**Out of scope.** Changes to the run detail or compare pages. New run data beyond what Dagster and the existing run records already provide. Bulk actions on runs (cancel, re-run). Sorting by arbitrary column. The light-theme navigation fix (#12), which is already done.

**Null action.** If Target or Launched by cannot be obtained from Dagster for historical runs, show `—` for those rows rather than guessing, and populate them for new runs. If consolidating the Settings page into the modal turns out to need more than a move of existing controls, ship the navigation change with the modal linking to the existing page, and consolidate in a follow-up.

**Decisions to confirm when this is specified.**
- The source issues give a column list without Status or Checks, while two others ask for both. This brief keeps both; their position in the column order is a proposal.
- The tab set (All / In progress / Succeeded / Failed) is a proposal modelled on Dagster; the source issue asks only for "a tabbed header".
- Whether the home page (where the logo links) stays as it is today or becomes Runs, now that Runs leads the navigation. The source issues only say the logo links home.

**Source issues.** #14, #163, #164, #165, #166, #167, #168, #169, #170, #171 (open) and #12 (closed, completed).
