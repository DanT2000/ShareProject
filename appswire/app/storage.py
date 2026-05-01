import re
import shutil
from pathlib import Path

from app.database import _default_storage

STORAGE_ROOT = _default_storage
STORAGE_ROOT.mkdir(parents=True, exist_ok=True)
(STORAGE_ROOT / "projects").mkdir(exist_ok=True)

MAX_UPLOAD_SIZE = 200 * 1024 * 1024  # 200 MB
ALLOWED_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".ico"}


def get_project_dir(project_id: int) -> Path:
    return STORAGE_ROOT / "projects" / str(project_id)


def get_files_dir(project_id: int) -> Path:
    return get_project_dir(project_id) / "files"


def safe_filename(filename: str) -> str:
    name = re.sub(r'[/\\:*?"<>|]', "_", filename)
    name = re.sub(r"\.\.+", ".", name)
    name = name.strip(". ")
    name = name[:200]
    return name or "file"


def save_project_image(project_id: int, upload_file) -> str:
    ext = Path(upload_file.filename).suffix.lower()
    if ext not in ALLOWED_IMAGE_EXTS:
        raise ValueError(f"Unsupported image format: {ext}")
    project_dir = get_project_dir(project_id)
    project_dir.mkdir(parents=True, exist_ok=True)
    for f in project_dir.glob("image.*"):
        f.unlink(missing_ok=True)
    image_path = project_dir / f"image{ext}"
    data = upload_file.file.read()
    image_path.write_bytes(data)
    return str(image_path.relative_to(STORAGE_ROOT))


def save_project_file(project_id: int, upload_file) -> str:
    files_dir = get_files_dir(project_id)
    files_dir.mkdir(parents=True, exist_ok=True)
    filename = safe_filename(upload_file.filename or "file")
    file_path = files_dir / filename
    data = upload_file.file.read()
    file_path.write_bytes(data)
    return str(file_path.relative_to(STORAGE_ROOT))


def delete_project_storage(project_id: int) -> None:
    project_dir = get_project_dir(project_id)
    if project_dir.exists():
        shutil.rmtree(project_dir)


def resolve_safe(relative_path: str) -> Path:
    """Resolve a storage-relative path, raising ValueError on traversal."""
    root = STORAGE_ROOT.resolve()
    target = (STORAGE_ROOT / relative_path).resolve()
    if not str(target).startswith(str(root)):
        raise ValueError("Path traversal detected")
    return target
