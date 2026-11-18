"""Bounded offline rehearsal of the feature participating-set contract.

Run with ``uv run pytest tests/test_feature_multi_repository.py``. Git repositories
are created under a temporary directory; no network or product checkout is used.
This verifies the coordination mechanics, not a real product pilot.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

ROOT = Path(__file__).resolve().parent.parent
CONTRACT = (
    ROOT / "plugins/v8ch/skills/feature-orchestrate/references/multi-repository.md"
)
GIT_ENV = {
    key: value for key, value in os.environ.items() if not key.startswith("GIT_")
}
GIT_ENV.update({"GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"})


def git(repo: Path, *args: str) -> str:
    return subprocess.check_output(
        ["git", "-C", str(repo), *args], text=True, env=GIT_ENV
    ).strip()


def make_repo(base: Path, name: str, value: str) -> Path:
    bare = base / f"{name}.git"
    subprocess.run(
        ["git", "init", "--bare", "--initial-branch=main", "-q", str(bare)],
        check=True,
        env=GIT_ENV,
    )
    repo = base / name
    subprocess.run(
        ["git", "clone", "-q", str(bare), str(repo)], check=True, env=GIT_ENV
    )
    git(repo, "config", "user.name", "Offline Test")
    git(repo, "config", "user.email", "offline@example.invalid")
    (repo / "part.txt").write_text(value)
    git(repo, "add", "part.txt")
    git(repo, "commit", "-qm", "init")
    git(repo, "push", "-q", "origin", "HEAD")
    git(repo, "switch", "-qc", "feature/demo")
    return repo


def heads(repos: dict[str, Path]) -> dict[str, str]:
    return {
        name: git(repo, "rev-parse", "HEAD") for name, repo in sorted(repos.items())
    }


def validate_set(expected: dict[str, str], live: dict[str, str]) -> None:
    if (
        expected != live
        or not expected
        or any(
            len(sha) != 40 or any(c not in "0123456789abcdef" for c in sha)
            for sha in expected.values()
        )
    ):
        raise ValueError("participating commit set mismatch")


def validate_claims(participating: dict[str, str], claims: dict[str, set[str]]) -> None:
    if not claims or any(
        not applicable or not applicable <= set(participating)
        for applicable in claims.values()
    ):
        raise ValueError("claim applicability mismatch")


def ordered_slices(
    slices: list[tuple[str, str, tuple[str, ...]]],
    gates: dict[str, list[tuple[str, bool]]],
    correction_budget: int = 3,
) -> list[str]:
    completed: list[str] = []
    for slice_id, owner, dependencies in slices:
        assert owner.startswith("v8chllc/")
        if not set(dependencies) <= set(completed):
            raise ValueError("predecessor incomplete")
        outcomes = gates[slice_id]
        if not outcomes:
            raise ValueError("slice gate result missing")
        failures = 0
        for builder, passed in outcomes:
            if builder != owner:
                raise ValueError("retained builder changed")
            if passed:
                break
            failures += 1
            if failures >= correction_budget:
                raise ValueError("slice correction budget exhausted")
        else:
            raise ValueError("failed slice holds advancement")
        completed.append(slice_id)
    return completed


def joint_proof(repos: dict[str, Path], frozen: dict[str, str]) -> str:
    validate_set(frozen, heads(repos))
    assert all(
        not git(repo, "status", "--porcelain", "--untracked-files=all")
        for repo in repos.values()
    ), "dirty checkout"
    # The assertion consumes actual files from both checked-out repositories.
    parts = {name: (repo / "part.txt").read_text() for name, repo in repos.items()}
    assert parts == {"v8chllc/alpha": "alpha-v2", "v8chllc/beta": "beta-v2"}
    validate_set(frozen, heads(repos))
    assert all(
        not git(repo, "status", "--porcelain", "--untracked-files=all")
        for repo in repos.values()
    ), "dirty checkout"
    return "joint check passed"


def pr_url(name: str) -> str:
    return f"https://github.com/{name}/pull/1"


def ready(
    frozen: dict[str, str],
    live: dict[str, str],
    results: dict[str, tuple[dict[str, str], str, str]],
) -> bool:
    validate_set(frozen, live)
    if set(results) != {pr_url(name) for name in frozen}:
        return False
    return all(
        commit_map == frozen
        and outcome == "pass"
        and result_url.startswith(f"{target_pr}#issuecomment-")
        for target_pr, (commit_map, outcome, result_url) in results.items()
    )


def test_two_repositories_joint_proof_and_publication_identity() -> None:
    rules = CONTRACT.read_text()
    for phrase in (
        "dependency DAG",
        "one eligible slice at a time",
        "One fresh verifier runs",
        "integrated harness once",
        "each affected pull request",
        "full 40-character commit SHAs",
    ):
        assert phrase in rules
    with TemporaryDirectory() as directory:
        base = Path(directory)
        repos = {
            "v8chllc/alpha": make_repo(base, "alpha", "alpha-v1"),
            "v8chllc/beta": make_repo(base, "beta", "beta-v1"),
        }
        slices = [
            ("A", "v8chllc/alpha", ()),
            ("B", "v8chllc/beta", ("A",)),
        ]
        # A failed gate is corrected by the retained owner before B advances.
        assert ordered_slices(
            slices,
            {
                "A": [("v8chllc/alpha", False), ("v8chllc/alpha", True)],
                "B": [("v8chllc/beta", True)],
            },
        ) == ["A", "B"]
        for name, repo in repos.items():
            (repo / "part.txt").write_text(f"{name.split('/')[-1]}-v2")
            git(repo, "add", "part.txt")
            git(repo, "commit", "-qm", "feature slice")
        frozen = heads(repos)
        claims = {
            "shared-independent": set(repos),
            "interaction": set(repos),
            "alpha-only": {"v8chllc/alpha"},
        }
        validate_claims(frozen, claims)
        with pytest.raises(ValueError, match="applicability"):
            validate_claims(frozen, {"interaction": {"v8chllc/outside"}})
        with pytest.raises(ValueError, match="applicability"):
            validate_claims(frozen, {"interaction": set()})
        assert joint_proof(repos, frozen) == "joint check passed"
        results: dict[str, tuple[dict[str, str], str, str]] = {
            pr_url(name): (frozen.copy(), "pass", f"{pr_url(name)}#issuecomment-21")
            for name in repos
        }
        assert ready(frozen, heads(repos), results)
        assert not ready(
            frozen,
            heads(repos),
            {pr_url("v8chllc/alpha"): results[pr_url("v8chllc/alpha")]},
        )
        for name in repos:
            target = pr_url(name)
            bad = results.copy()
            bad[target] = (frozen.copy(), "fail", f"{target}#issuecomment-21")
            assert not ready(frozen, heads(repos), bad)
            bad[target] = (
                {**frozen, name: "0" * 40},
                "pass",
                f"{target}#issuecomment-21",
            )
            assert not ready(frozen, heads(repos), bad)
            other = next(repo_name for repo_name in repos if repo_name != name)
            bad[target] = (frozen.copy(), "pass", f"{pr_url(other)}#issuecomment-21")
            assert not ready(frozen, heads(repos), bad)
        with pytest.raises(ValueError, match="mismatch"):
            validate_set({"v8chllc/alpha": frozen["v8chllc/alpha"][:8]}, heads(repos))
        for name, repo in repos.items():
            (repo / "part.txt").write_text(f"{name}-moved")
            git(repo, "add", "part.txt")
            git(repo, "commit", "-qm", "head moved")
            with pytest.raises(ValueError, match="mismatch"):
                joint_proof(repos, frozen)
            with pytest.raises(ValueError, match="mismatch"):
                ready(frozen, heads(repos), results)
            git(repo, "reset", "--hard", frozen[name])


def test_failed_slice_holds_queue_and_budget_exhaustion() -> None:
    slices = [("A", "v8chllc/alpha", ()), ("B", "v8chllc/beta", ("A",))]
    with pytest.raises(ValueError, match="holds advancement"):
        ordered_slices(
            slices, {"A": [("v8chllc/alpha", False)], "B": [("v8chllc/beta", True)]}
        )
    with pytest.raises(ValueError, match="budget exhausted"):
        ordered_slices(
            slices, {"A": [("v8chllc/alpha", False)] * 3, "B": [("v8chllc/beta", True)]}
        )
    with pytest.raises(ValueError, match="gate result missing"):
        ordered_slices(slices, {"A": [], "B": [("v8chllc/beta", True)]})
    with pytest.raises(ValueError, match="retained builder changed"):
        ordered_slices(
            slices, {"A": [("v8chllc/beta", True)], "B": [("v8chllc/beta", True)]}
        )
    with pytest.raises(ValueError, match="predecessor incomplete"):
        ordered_slices([slices[1]], {"B": [("v8chllc/beta", True)]})


def test_one_member_set_preserves_single_repository_case() -> None:
    one = {"v8chllc/alpha": "a" * 40}
    validate_set(one, one.copy())
    assert ordered_slices(
        [("A", "v8chllc/alpha", ())], {"A": [("v8chllc/alpha", True)]}
    ) == ["A"]
    assert ready(
        one,
        one.copy(),
        {
            pr_url("v8chllc/alpha"): (
                one.copy(),
                "pass",
                f"{pr_url('v8chllc/alpha')}#issuecomment-21",
            )
        },
    )


def test_joint_proof_rejects_missing_interaction_even_at_matching_heads() -> None:
    with TemporaryDirectory() as directory:
        base = Path(directory)
        repos = {
            "v8chllc/alpha": make_repo(base, "alpha", "alpha-v2"),
            "v8chllc/beta": make_repo(base, "beta", "beta-wrong"),
        }
        with pytest.raises(AssertionError):
            joint_proof(repos, heads(repos))


def test_git_helpers_ignore_inherited_git_location(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with TemporaryDirectory() as directory:
        base = Path(directory)
        repo = make_repo(base, "alpha", "alpha-v1")
        monkeypatch.setenv("GIT_DIR", str(base / "wrong.git"))
        monkeypatch.setenv("GIT_WORK_TREE", str(base / "wrong-tree"))
        monkeypatch.setenv("GIT_INDEX_FILE", str(base / "wrong-index"))
        assert len(git(repo, "rev-parse", "HEAD")) == 40


def test_joint_proof_rejects_dirty_checkout_at_same_commit() -> None:
    with TemporaryDirectory() as directory:
        base = Path(directory)
        repos = {
            "v8chllc/alpha": make_repo(base, "alpha", "alpha-v2"),
            "v8chllc/beta": make_repo(base, "beta", "beta-v2"),
        }
        frozen = heads(repos)
        alpha = repos["v8chllc/alpha"]
        (alpha / "part.txt").write_text("uncommitted change")
        with pytest.raises(AssertionError, match="dirty checkout"):
            joint_proof(repos, frozen)
        git(alpha, "add", "part.txt")
        with pytest.raises(AssertionError, match="dirty checkout"):
            joint_proof(repos, frozen)
        git(alpha, "reset", "--hard", frozen["v8chllc/alpha"])
        extra = alpha / "extra.txt"
        extra.write_text("untracked")
        with pytest.raises(AssertionError, match="dirty checkout"):
            joint_proof(repos, frozen)


def test_joint_proof_rejects_checkout_dirtied_during_proof(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with TemporaryDirectory() as directory:
        base = Path(directory)
        repos = {
            "v8chllc/alpha": make_repo(base, "alpha", "alpha-v2"),
            "v8chllc/beta": make_repo(base, "beta", "beta-v2"),
        }
        frozen = heads(repos)
        original = Path.read_text

        def read_and_dirty(path: Path) -> str:
            result = original(path)
            if path == repos["v8chllc/beta"] / "part.txt":
                (repos["v8chllc/alpha"] / "part.txt").write_text("late edit")
            return result

        with monkeypatch.context() as patch:
            patch.setattr(Path, "read_text", read_and_dirty)
            with pytest.raises(AssertionError, match="dirty checkout"):
                joint_proof(repos, frozen)
