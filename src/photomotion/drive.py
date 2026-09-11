"""Drive adapter interface. Local folder ships in v1; Drive MCP is optional."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil


@dataclass
class DriveItem:
    id: str
    name: str
    mime_type: str
    is_folder: bool


class DriveAdapter:
    def list_folder(self, folder_id: str) -> list[DriveItem]:
        raise NotImplementedError

    def download(self, file_id: str, dest: Path) -> Path:
        raise NotImplementedError

    def create_folder(self, name: str, parent_id: str | None = None) -> str:
        raise NotImplementedError

    def upload(self, local: Path, folder_id: str, name: str | None = None) -> str:
        raise NotImplementedError


class LocalFolderAdapter(DriveAdapter):
    """Treats a filesystem directory as INBOX / DELIVER."""

    def __init__(self, root: Path):
        self.root = Path(root)

    def list_folder(self, folder_id: str) -> list[DriveItem]:
        d = self.root / folder_id if folder_id not in (".", "") else self.root
        items = []
        for p in sorted(d.iterdir()):
            items.append(
                DriveItem(
                    id=str(p),
                    name=p.name,
                    mime_type="application/vnd.google-apps.folder" if p.is_dir() else "image/jpeg",
                    is_folder=p.is_dir(),
                )
            )
        return items

    def download(self, file_id: str, dest: Path) -> Path:
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(file_id, dest)
        return dest

    def create_folder(self, name: str, parent_id: str | None = None) -> str:
        parent = Path(parent_id) if parent_id else self.root
        path = parent / name
        path.mkdir(parents=True, exist_ok=True)
        return str(path)

    def upload(self, local: Path, folder_id: str, name: str | None = None) -> str:
        dest = Path(folder_id) / (name or local.name)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(local, dest)
        return str(dest)


def write_deliver_bundle(job_deliver: Path, dest_folder: Path, adapter: DriveAdapter) -> list[str]:
    written = []
    dest_id = adapter.create_folder(dest_folder.name, str(dest_folder.parent))
    for name in (
        "master_16x9_clean.mp4",
        "vertical_9x16_clean.mp4",
        "square_1x1_clean.mp4",
        "plan.json",
        "cut_list.json",
    ):
        src = job_deliver / name
        if src.exists():
            written.append(adapter.upload(src, dest_id, name))
    return written
