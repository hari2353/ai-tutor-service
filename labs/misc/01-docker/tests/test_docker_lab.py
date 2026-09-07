"""Lab 01 tests. Pure stdlib, no sleeps, no docker binary — everything is simulated."""
import pytest


# ------------------------------------------------------------------ parser
def test_parse_basic_and_comments(D):
    text = """
    # comment line
    FROM python:3.13-slim

    RUN pip install -r requirements.txt
    """
    instrs = D.parse_dockerfile(text)
    assert [i["instruction"] for i in instrs] == ["FROM", "RUN"]
    assert instrs[0]["args"] == ["python:3.13-slim"]
    assert instrs[1]["args"] == ["pip", "install", "-r", "requirements.txt"]


def test_parse_line_continuation(D):
    text = ("RUN apt-get update && \\\n"
            " # a comment INSIDE the continuation\n"
            "    apt-get install -y curl && \\\n"
            "    apt-get clean")
    instrs = D.parse_dockerfile(text)
    assert len(instrs) == 1
    assert instrs[0]["instruction"] == "RUN"
    assert instrs[0]["args"] == ["apt-get", "update", "&&",
                                "apt-get", "install", "-y", "curl", "&&",
                                "apt-get", "clean"]
    assert "  " not in instrs[0]["raw"]


def test_parse_case_insensitive_and_exec_form(D):
    text = ("from alpine:3.20\n"
            "cmd [\"/bin/sh\", \"-c\", \"echo hi\"]\n"
            "entrypoint [\"python\"]\n")
    instrs = D.parse_dockerfile(text)
    assert [i["instruction"] for i in instrs] == ["FROM", "CMD", "ENTRYPOINT"]
    assert instrs[1]["args"] == ["/bin/sh", "-c", "echo hi"]
    assert instrs[2]["args"] == ["python"]


def test_parse_all_known_instructions_roundtrip(D):
    text = ("\n".join([
        "FROM python:3.13-slim",
        "ARG VERSION=1.0",
        "ENV PYTHONDONTWRITEBYTECODE=1",
        "WORKDIR /app",
        "COPY . .",
        "RUN python -m compileall .",
        "EXPOSE 8000",
        "USER app",
        "ENTRYPOINT [\"python\"]",
        "CMD [\"app.py\"]",
    ]))
    instrs = D.parse_dockerfile(text)
    assert [i["instruction"] for i in instrs] == [
        "FROM", "ARG", "ENV", "WORKDIR", "COPY", "RUN", "EXPOSE", "USER",
        "ENTRYPOINT", "CMD"]
    for i in instrs:
        assert set(i.keys()) >= {"instruction", "args", "raw"}
        assert isinstance(i["args"], list)


# ------------------------------------------------------------------ layer cache
DOCKERFILE = """
FROM python:3.13-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY app.py .
CMD ["python", "app.py"]
"""


def _parse(D, text=DOCKERFILE):
    return D.parse_dockerfile(text)


def test_first_build_all_misses_second_identical_all_hits(D):
    cache = D.LayerCache()
    r1 = cache.build(_parse(D))
    assert (r1.cache_hits, r1.cache_misses) == (0, 6)
    r2 = cache.build(_parse(D))
    assert (r2.cache_hits, r2.cache_misses) == (6, 0)
    assert all(layer["cached"] for layer in r2.image_layers)


def test_one_run_changed_cascades_misses_after_it(D):
    cache = D.LayerCache()
    cache.build(_parse(D))          # baseline
    changed = D.parse_dockerfile(DOCKERFILE.replace(
        "pip install -r requirements.txt", "pip install --no-cache-dir -r requirements.txt"))
    r = cache.build(changed)
    # first 3 layers unchanged -> hits; the changed RUN and everything after -> misses
    assert [layer["cached"] for layer in r.image_layers] == [
        True, True, True, False, False, False]
    assert (r.cache_hits, r.cache_misses) == (3, 3)


def test_earlier_layer_change_invalidates_even_identical_later_layers(D):
    cache = D.LayerCache()
    cache.build(_parse(D))
    changed = D.parse_dockerfile(DOCKERFILE.replace(
        "WORKDIR /app", "WORKDIR /srv"))
    r = cache.build(changed)
    assert [layer["cached"] for layer in r.image_layers] == [
        True, False, False, False, False, False]
    # the identical COPY/RUN/CMD after it did not hit — cascade, not per-instruction
    assert (r.cache_hits, r.cache_misses) == (1, 5)


def test_copy_content_change_misses_same_content_hits(D):
    cache = D.LayerCache()
    files = {"requirements.txt": "flask==3.0.0\n", "app.py": "print('hi')"}
    cache.build(_parse(D), files)
    # same paths, same content -> all hits
    r2 = cache.build(_parse(D), files)
    assert (r2.cache_hits, r2.cache_misses) == (6, 0)
    # content of an EARLIER COPY changes -> miss from that layer on
    files2 = dict(files, **{"requirements.txt": "flask==3.1.0\n"})
    r3 = cache.build(_parse(D), files2)
    assert [layer["cached"] for layer in r3.image_layers] == [
        True, True, False, False, False, False]


def test_layer_digests_are_content_addressed(D):
    cache = D.LayerCache()
    r1 = cache.build(_parse(D))
    cache2 = D.LayerCache()
    r2 = cache2.build(_parse(D))
    assert [l["digest"] for l in r1.image_layers] == [l["digest"] for l in r2.image_layers]
    assert len({l["digest"] for l in r1.image_layers}) == 6
    changed = D.parse_dockerfile(DOCKERFILE.replace("app.py .", "server.py ."))
    r3 = cache.build(changed)
    assert r3.image_layers[4]["digest"] != r1.image_layers[4]["digest"]


def test_cache_track_per_position(D):
    """Same instruction at a DIFFERENT position must not hit."""
    cache = D.LayerCache()
    cache.build(_parse(D))
    reordered = D.parse_dockerfile("""
FROM python:3.13-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
RUN echo extra
COPY app.py .
CMD ["python", "app.py"]
""")
    r = cache.build(reordered)
    # positions 0-3 match; inserted RUN breaks the cascade for 4-5
    assert [l["cached"] for l in r.image_layers][:4] == [True, True, True, True]
    assert r.image_layers[5]["cached"] is False


# ------------------------------------------------------------------ linter
def _codes(findings):
    return [f["code"] for f in findings]


def test_lint_clean_dockerfile_passes(D):
    instrs = D.parse_dockerfile("""
FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1
WORKDIR /app
USER app
COPY requirements.txt .
RUN pip install -r requirements.txt
EXPOSE 8000
ENTRYPOINT ["python"]
CMD ["app.py"]
""")
    assert D.lint_dockerfile(instrs) == []


def test_lint_latest_tag_warns_and_pinned_passes(D):
    bad = D.parse_dockerfile("FROM python:latest\nEXPOSE 80\nUSER app")
    assert "W001" in _codes(D.lint_dockerfile(bad))
    notag = D.parse_dockerfile("FROM python\nEXPOSE 80\nUSER app")
    assert "W001" in _codes(D.lint_dockerfile(notag))
    ok = D.parse_dockerfile("FROM python:3.13-slim\nEXPOSE 80\nUSER app")
    assert "W001" not in _codes(D.lint_dockerfile(ok))
    digest = D.parse_dockerfile("FROM python@sha256:abc123\nEXPOSE 80\nUSER app")
    assert "W001" not in _codes(D.lint_dockerfile(digest))


def test_lint_missing_expose_warns(D):
    instrs = D.parse_dockerfile("FROM alpine:3.20\nUSER app")
    assert "W002" in _codes(D.lint_dockerfile(instrs))


def test_lint_running_as_root_warns_and_user_fixes(D):
    root = D.parse_dockerfile("FROM alpine:3.20\nRUN whoami\nEXPOSE 80")
    assert "W003" in _codes(D.lint_dockerfile(root))
    fixed = D.parse_dockerfile("FROM alpine:3.20\nUSER app\nRUN whoami\nEXPOSE 80")
    assert "W003" not in _codes(D.lint_dockerfile(fixed))


def test_lint_two_entrypoints_errors(D):
    instrs = D.parse_dockerfile(
        "FROM alpine:3.20\nENTRYPOINT [\"sh\"]\nENTRYPOINT [\"bash\"]\nUSER app\nEXPOSE 80")
    findings = D.lint_dockerfile(instrs)
    assert "E001" in _codes(findings)
    assert any(f["severity"] == "ERROR" for f in findings)


def test_lint_instruction_before_from_errors_arg_exempt(D):
    bad = D.parse_dockerfile("RUN echo hi\nFROM alpine:3.20\nUSER app\nEXPOSE 80")
    assert "E002" in _codes(D.lint_dockerfile(bad))
    ok = D.parse_dockerfile("ARG VERSION=1\nFROM alpine:3.20\nUSER app\nEXPOSE 80")
    assert D.lint_dockerfile(ok) == []


def test_lint_no_from_errors(D):
    instrs = D.parse_dockerfile("RUN echo hi")
    assert "E003" in _codes(D.lint_dockerfile(instrs))


def test_lint_duplicate_cmd_and_secret_env_warn(D):
    instrs = D.parse_dockerfile(
        "FROM alpine:3.20\nCMD [\"a\"]\nCMD [\"b\"]\n"
        "ENV AWS_SECRET_ACCESS_KEY=abc\nUSER app\nEXPOSE 80")
    codes = _codes(D.lint_dockerfile(instrs))
    assert "W004" in codes
    assert "W005" in codes


# ------------------------------------------------------------------ command knowledge
def test_docker_command_help_covers_the_core(D):
    for cmd in ["run", "ps", "exec", "logs", "inspect", "images", "pull", "build",
                "tag", "push", "cp", "stats", "system prune", "network create", "volume ls"]:
        desc = D.docker_command_help(cmd)
        assert isinstance(desc, str) and len(desc) > 5


def test_docker_command_help_strips_prefix_and_is_case_insensitive(D):
    assert D.docker_command_help("docker run") == D.docker_command_help("RUN")


def test_docker_command_help_unknown_raises(D):
    with pytest.raises(KeyError):
        D.docker_command_help("dance")
    with pytest.raises(KeyError):
        D.docker_command_help("docker rm -f")  # rm is real docker but not in our core 15


# ------------------------------------------------------------------ exit codes
def test_exit_code_decoder_known_codes(D):
    assert "ok" in D.exit_code_decoder(0).lower()
    assert "application" in D.exit_code_decoder(1).lower()
    assert "daemon" in D.exit_code_decoder(125).lower()
    assert "not executable" in D.exit_code_decoder(126).lower()
    assert "not found" in D.exit_code_decoder(127).lower()
    assert "sigkill" in D.exit_code_decoder(137).lower()
    assert "oom" in D.exit_code_decoder(137).lower()
    assert "sigterm" in D.exit_code_decoder(143).lower()


def test_exit_code_decoder_128_plus_n(D):
    """137 = 128+9 (SIGKILL), 143 = 128+15 (SIGTERM) — the pattern an interviewer wants."""
    for code, sig in [(137, 9), (143, 15)]:
        desc = D.exit_code_decoder(code)
        assert str(128 + sig) in desc or str(sig) in desc


def test_exit_code_decoder_unknown_raises(D):
    with pytest.raises(KeyError):
        D.exit_code_decoder(2)
    with pytest.raises(KeyError):
        D.exit_code_decoder(999)
