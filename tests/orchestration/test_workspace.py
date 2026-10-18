"""FR-O11, AMB-10 / ADR-010: the run workspace is the autonomy boundary; rollback really reverts."""

from __future__ import annotations

from pathlib import Path

import pytest

from agentic_sdlc.orchestration.workspace import ChangeSet, FileChange, Workspace, WorkspaceError

pytestmark = pytest.mark.orchestration


@pytest.fixture
def ws(tmp_path: Path) -> Workspace:
    return Workspace(tmp_path / "runs" / "run-1" / "workspace")


@pytest.mark.req("FR-O11")
def test_apply_creates_and_modifies_files_and_records_inverse(ws: Workspace) -> None:
    ws.write("src/app.py", "print('v1')\n")
    change = ChangeSet(
        id="cs-1",
        changes=[
            FileChange(path="src/app.py", content="print('v2')\n"),
            FileChange(path="src/new.py", content="x = 1\n"),
        ],
    )
    receipt = ws.apply(change)
    assert ws.read("src/app.py") == "print('v2')\n" and ws.read("src/new.py") == "x = 1\n"
    assert receipt.inverse["src/app.py"] == "print('v1')\n"
    assert receipt.inverse["src/new.py"] is None  # did not exist before -> inverse is delete
    assert receipt.files_changed == ["src/app.py", "src/new.py"]


@pytest.mark.req("FR-O11", "AMB-10")
def test_revert_restores_exact_prior_state(ws: Workspace) -> None:
    ws.write("a.txt", "one\n")
    receipt = ws.apply(
        ChangeSet(id="cs", changes=[FileChange("a.txt", "two\n"), FileChange("b.txt", "new\n")])
    )
    outcome = ws.revert(receipt)
    assert ws.read("a.txt") == "one\n"
    assert not ws.exists("b.txt")
    assert outcome == {
        "rollback": True,
        "restored": ["a.txt"],
        "removed": ["b.txt"],
        "change_set": "cs",
    }


@pytest.mark.req("FR-O11")
def test_delete_change_and_its_rollback(ws: Workspace) -> None:
    ws.write("gone.txt", "bye\n")
    receipt = ws.apply(ChangeSet(id="cs", changes=[FileChange("gone.txt", None)]))
    assert not ws.exists("gone.txt")
    ws.revert(receipt)
    assert ws.read("gone.txt") == "bye\n"


@pytest.mark.req("FR-O11")
def test_workspace_never_escapes_its_root(ws: Workspace) -> None:
    for bad in ("../outside.txt", "/etc/passwd", "src/../../x", "..\\win"):
        with pytest.raises(WorkspaceError):
            ws.apply(ChangeSet(id="cs", changes=[FileChange(bad, "nope")]))
    assert not (ws.root.parent / "outside.txt").exists()


@pytest.mark.req("FR-O11")
def test_apply_is_atomic_per_change_set(ws: Workspace) -> None:
    ws.write("ok.txt", "orig\n")
    with pytest.raises(WorkspaceError):
        ws.apply(
            ChangeSet(
                id="cs", changes=[FileChange("ok.txt", "changed\n"), FileChange("../bad", "x")]
            )
        )
    assert ws.read("ok.txt") == "orig\n"  # first change rolled back


@pytest.mark.req("ADR-010")
def test_seed_copies_selected_repository_files_read_only(ws: Workspace, tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True)
    (repo / "src" / "m.py").write_text("v = 1\n")
    (repo / "secret.env").write_text("KEY=x\n")
    copied = ws.seed_from(repo, ["src/m.py"])
    assert copied == ["src/m.py"] and ws.read("src/m.py") == "v = 1\n"
    assert not ws.exists("secret.env")
    ws.write("src/m.py", "v = 2\n")
    assert (repo / "src" / "m.py").read_text() == "v = 1\n"  # the repository is untouched
