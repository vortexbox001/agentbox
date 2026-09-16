"""The run viewer is strictly read-only (spec 012 FR-024, T050a).

Every run/viewer route is GET-only, there is no route that mutates run data, and there is no
live-streaming endpoint (the viewer is post-run, disk-only).
"""
import main


def _viewer_routes():
    for r in main.app.routes:
        path = getattr(r, "path", "")
        if path.startswith("/runs") or path.startswith("/api/runs"):
            yield path, set(getattr(r, "methods", set()) or set())


def test_all_viewer_routes_are_get_only():
    routes = list(_viewer_routes())
    assert routes, "no viewer routes registered"
    for path, methods in routes:
        mutating = methods & {"POST", "PUT", "PATCH", "DELETE"}
        assert not mutating, f"{path} exposes mutating methods {mutating} — the viewer is read-only"


def test_no_run_mutation_or_stream_route():
    paths = [p for p, _ in _viewer_routes()]
    # no obviously mutating or streaming verbs in any viewer path
    for p in paths:
        low = p.lower()
        for banned in ("delete", "prune", "stream", "ws", "edit", "rerun", "retry", "cancel"):
            assert banned not in low, f"viewer route {p} looks like a mutation/stream ({banned})"
