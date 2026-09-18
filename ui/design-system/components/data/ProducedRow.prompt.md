ProducedRow lists something a run produced outside `/output`, mined best-effort from the event
stream: a kind label (Pull request / Commit / File), the identifier in mono (URL / short SHA /
path), and an Open/Preview action when derivable. Rows are grouped PRs → commits → files.
```jsx
<ProducedRow kind="pull_request" identifier="https://github.com/o/r/pull/7" action="https://github.com/o/r/pull/7" />
```
