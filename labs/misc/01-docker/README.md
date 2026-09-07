# Lab 01: Docker Without Docker — Semantics, Layers, Lint

**Track:** T12 DevOps, Infra & Security · **Time:** 2.5h · **XP:** 50
**Module:** `T12-docker`

**You will build:** a Dockerfile parser, a layer-cache simulator that reproduces BuildKit's invalidation cascade, an 8-rule Dockerfile linter, and the exit-code / command knowledge scaffolding — pure Python, no Docker installed.

**You will be able to answer:** *"Why did my 30-second build become 8 minutes after one commit — and where does a secret leaked into an image actually live?"*

## Setup

```bash
cd labs/misc/01-docker
python -m venv .venv && . .venv/bin/activate     # or: uv venv && . .venv/bin/activate
pip install pytest                                # only dependency
```

## The spec

1. **`parse_dockerfile(text)`** → a list of `{instruction, args, raw}` dicts, one per instruction.
   - Full-line comments and blank lines never become instructions.
   - A trailing `\` continues the instruction onto the next line: continuation segments are joined with single spaces, backslashes dropped; comment lines inside a continuation are dropped too.
   - Instruction keywords are case-insensitive and normalized to upper case (`from` → `FROM`).
   - `CMD`/`ENTRYPOINT` exec form (`["python", "app.py"]`) parses as a JSON list of strings; every other instruction's args are whitespace-split.
   - `raw` is the normalized logical line.
   - Supported instructions: `FROM RUN COPY ENV EXPOSE CMD ENTRYPOINT WORKDIR USER ARG` — anything else still parses (you are not the Docker daemon).
2. **`LayerCache.build(instructions, files=None)`** → `BuildResult(image_layers, cache_hits, cache_misses)` — a `NamedTuple`: unpack it or use attributes.
   - Every instruction produces exactly one layer; `image_layers[k]["digest"]` is a hex digest of the layer's cache key.
   - Layer `i` is a **hit** iff its key is identical to the *previous build's* layer at the same position **and** every earlier layer also hit. The key is `(instruction, args)` — except `COPY`, whose key also includes a content hash of the source paths resolved against the `files` dict `{path: content}` (a missing path hashes as empty).
   - The first build has no previous build: every layer misses.
   - One miss cascades: every later layer misses even when unchanged. **Instruction order is a build-time decision.**
3. **`lint_dockerfile(instructions)`** → a list of `{severity, code, message}` findings:

   | Severity | Code | Rule | Fires when |
   |---|---|---|---|
   | ERROR | E001 | `TWO_ENTRYPOINTS` | more than one ENTRYPOINT (once per file) |
   | ERROR | E002 | `BEFORE_FROM` | a non-ARG instruction appears before the first FROM |
   | ERROR | E003 | `MISSING_FROM` | no FROM at all (E002 is then not double-reported) |
   | WARN | W001 | `LATEST_TAG` | `FROM x:latest`, or `FROM x` with no tag or digest — once per unpinned FROM |
   | WARN | W002 | `NO_EXPOSE` | no EXPOSE anywhere |
   | WARN | W003 | `ROOT_USER` | no USER before the first RUN |
   | WARN | W004 | `DUPLICATE_CMD` | more than one CMD — the earlier ones are dead code (once per file) |
   | WARN | W005 | `SECRET_IN_ENV` | an ENV key looks like a secret (`SECRET`, `PASSWORD`, `TOKEN`, `…_KEY`) — once per offending ENV |

4. **`docker_command_help(cmd)`** → a real one-line description for each of the 15 core commands: `run ps exec logs inspect images pull build tag push cp stats system prune network create volume ls`. A leading `docker ` is stripped and case is normalized; anything unknown raises `KeyError`.
5. **`exit_code_decoder(code)`** → the meaning of `0 1 125 126 127 137 143` (137 is SIGKILL/OOM, 143 SIGTERM); unknown codes raise `KeyError`.

## Run the tests

```bash
python -m pytest tests -q                 # against starter/ → FAILS. Make them pass.
python -m pytest tests -q --solution      # the reference — all green
```

## Stretch goals

1. **Cache mounts** — teach `build()` a `--mount=type=cache` RUN: it hits even when its own layer is invalidated. *("Why does pip still hit cache after requirements.txt changes?")*
2. **Multi-stage** — support `FROM … AS build` + `COPY --from=build` and report which layers ship in the final image. *("Why is the final image 20MB when the build needed 900MB?")*
3. **Parent-chained digests** — fold the parent digest into each layer's digest so any change breaks every descendant digest, like real content-addressed storage. *("Prove the cascade with digests, not positions.")*
4. **hadolint parity** — add three real rules (DL3008 pin apt packages, DL3016 pin npm, DL3059 no consecutive RUNs). *("What does a production linter check that yours doesn't?")*
