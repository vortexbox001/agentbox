**Intent.** Extract a single `agent-base` image with the OS, non-root user, git, and the common command-line tools every agent tends to need, and rebuild each harness image as a thin layer on top. Adding a tool for all agents becomes a one-line change in one place; Pi builds get smaller and faster. No agent YAML changes.

**What changes.**
- New `images/agent-base/` (Debian slim + Node 20, since three harnesses need Node): installs `git`, `curl`, `ca-certificates`, `ripgrep`, `jq`, the GitHub CLI (`gh`), `unzip`, and standard build essentials; creates the uid-1000 `node` user the harness images already assume; sets `WORKDIR /workspace`. Tagged `agentbox/agent-base`.
- `agent-claude`, `agent-pi`, `agent-codex` change to `FROM agentbox/agent-base` and drop their duplicated `apt-get`/user/workdir lines, keeping only the harness install (`npm install -g …`), entrypoint, and harness-specific env (`CODEX_HOME`). `agent-python` stays on `python:3.12-slim` (the api runner needs no shell tools) unless the plan finds it benefits.
- README build steps and `scripts/bootstrap.sh` build `agent-base` first, then the harness images. Compose notes updated if they reference builds.
- The common tool list lives in exactly one Dockerfile; each harness image carries a one-line comment pointing at the base.

**What I'd check.**
- Build `agent-base`, then the four harness images; none contains its own `apt-get git curl` line. `docker run --rm agentbox/agent-claude which rg jq gh git` prints paths; same for `agent-pi` and `agent-codex`.
- Run an existing agent of each harness end to end; behavior identical (same report, same output).
- Combined harness image size is smaller (shared layer), per `docker image ls`.
- Add `yq` to `agent-base`, rebuild base and one harness; the tool is present with no change to the harness Dockerfile.

**Out of scope.** Per-agent images. Runtime tool installation (022). Changing which harness images exist. Language toolchains beyond the common set.

**Null action.** If a harness genuinely can't use the shared base, leave that one on its own base and document why, rather than forcing a lowest-common-denominator base that bloats the others.