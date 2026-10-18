"""Run workspace — where the implementation agent is allowed to write (ADR-010).

Every file operation is confined to ``data/runs/<run_id>/workspace``. Applying a
``ChangeSet`` records the inverse of every change, so the engine can perform a
true *rollback* (restore prior bytes) when a downstream gate rejects the work
(FR-O11, AMB-10). Promoting a change set into the real repository is a human
act outside this system — that is the controlled-autonomy boundary.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any


class WorkspaceError(ValueError):
    pass


@dataclass(frozen=True)
class FileChange:
    path: str
    content: str | None  # None = delete


@dataclass
class ChangeSet:
    id: str
    changes: list[FileChange] = field(default_factory=list)
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "description": self.description,
            "changes": [
                {
                    "path": c.path,
                    "action": "delete" if c.content is None else "write",
                    "bytes": len(c.content or ""),
                }
                for c in self.changes
            ],
        }


@dataclass
class ApplyReceipt:
    change_set: str
    files_changed: list[str]
    inverse: dict[str, str | None]  # path -> previous content (None = did not exist)

    def to_dict(self) -> dict[str, Any]:
        return {
            "change_set": self.change_set,
            "files_changed": self.files_changed,
            "inverse": {p: (None if v is None else len(v)) for p, v in self.inverse.items()},
        }


class Workspace:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    # --- path safety ---------------------------------------------------------

    def _resolve(self, rel: str) -> Path:
        if not rel or rel.startswith(("/", "\\")) or "\\" in rel:
            raise WorkspaceError(f"path {rel!r} must be relative and use '/'")
        parts = PurePosixPath(rel).parts
        if any(p in {"..", ""} for p in parts):
            raise WorkspaceError(f"path {rel!r} may not contain '..'")
        target = (self.root / rel).resolve()
        if self.root != target and self.root not in target.parents:
            raise WorkspaceError(f"path {rel!r} escapes the workspace")
        return target

    # --- basic I/O -------------------------------------------------------------

    def exists(self, rel: str) -> bool:
        return self._resolve(rel).exists()

    def read(self, rel: str) -> str:
        return self._resolve(rel).read_text(encoding="utf-8")

    def write(self, rel: str, content: str) -> None:
        target = self._resolve(rel)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

    def delete(self, rel: str) -> None:
        target = self._resolve(rel)
        if target.exists():
            target.unlink()

    def listdir(self) -> list[str]:
        if not self.root.exists():
            return []
        return sorted(
            str(p.relative_to(self.root).as_posix()) for p in self.root.rglob("*") if p.is_file()
        )

    # --- change sets -------------------------------------------------------------

    def apply(self, change_set: ChangeSet) -> ApplyReceipt:
        """Apply all changes or none; return the receipt needed to roll back."""
        self.root.mkdir(parents=True, exist_ok=True)
        inverse: dict[str, str | None] = {}
        applied: list[str] = []
        try:
            for change in change_set.changes:
                target = self._resolve(change.path)
                inverse.setdefault(
                    change.path, target.read_text(encoding="utf-8") if target.exists() else None
                )
                if change.content is None:
                    if target.exists():
                        target.unlink()
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_text(change.content, encoding="utf-8")
                applied.append(change.path)
        except WorkspaceError:
            self._restore(inverse)
            raise
        return ApplyReceipt(change_set=change_set.id, files_changed=applied, inverse=inverse)

    def revert(self, receipt: ApplyReceipt) -> dict[str, Any]:
        restored, removed = self._restore(receipt.inverse)
        return {
            "rollback": True,
            "restored": restored,
            "removed": removed,
            "change_set": receipt.change_set,
        }

    def _restore(self, inverse: dict[str, str | None]) -> tuple[list[str], list[str]]:
        restored: list[str] = []
        removed: list[str] = []
        for rel, previous in inverse.items():
            target = self._resolve(rel)
            if previous is None:
                if target.exists():
                    target.unlink()
                    removed.append(rel)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(previous, encoding="utf-8")
                restored.append(rel)
        return sorted(restored), sorted(removed)

    # --- seeding from the repository (read-only copy) -----------------------------

    def seed_from(self, repository: Path, paths: list[str]) -> list[str]:
        copied: list[str] = []
        for rel in paths:
            source = (repository / rel).resolve()
            if repository.resolve() not in source.parents or not source.is_file():
                continue
            target = self._resolve(rel)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
            copied.append(rel)
        return copied

    def wipe(self) -> None:
        if self.root.exists():
            shutil.rmtree(self.root)
