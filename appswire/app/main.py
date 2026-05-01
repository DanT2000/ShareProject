import json
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

import markdown as md
from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db, init_db, SessionLocal
from app import models, auth
from app import storage as fstore

_HERE = Path(__file__).parent
_secret_key: Optional[str] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _secret_key
    init_db()
    db = SessionLocal()
    try:
        _secret_key = auth.get_or_create_secret_key(db)
        for key, value in [
            ("app_name", "AppsWire"),
            ("app_subtitle", "Applications · Tools · Experiments"),
        ]:
            if not db.query(models.Setting).filter(models.Setting.key == key).first():
                db.add(models.Setting(key=key, value=value))
        db.commit()
    finally:
        db.close()
    yield


app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None)

app.mount("/static", StaticFiles(directory=str(_HERE / "static")), name="static")
app.mount(
    "/media",
    StaticFiles(directory=str(fstore.STORAGE_ROOT)),
    name="media",
)

templates = Jinja2Templates(directory=str(_HERE / "templates"))


# ── helpers ──────────────────────────────────────────────────────────────────

def _secret() -> str:
    return _secret_key or ""


def _settings(db: Session) -> dict:
    return {s.key: s.value for s in db.query(models.Setting).all()}


def _session_uid(request: Request) -> Optional[int]:
    return auth.get_session_user(request, _secret())


def _project_to_dict(p: models.Project) -> dict:
    return {
        "id": p.id,
        "title": p.title,
        "description": p.description,
        "version": p.version,
        "is_published": p.is_published,
        "sort_order": p.sort_order,
        "image_mode": (
            "upload" if p.image_path else ("url" if p.image_url else "none")
        ),
        "image_url": p.image_url or "",
        "image_path": p.image_path or "",
        "instruction_md": p.instruction_md or "",
        "actions": [
            {
                "id": a.id,
                "kind": a.kind,
                "label": a.label,
                "url": a.url or "",
                "file_path": a.file_path or "",
                "file_name": a.file_path.split("/")[-1] if a.file_path else "",
                "is_primary": a.is_primary,
                "sort_order": a.sort_order,
            }
            for a in p.actions
        ],
    }


# ── public routes ─────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def index(request: Request, db: Session = Depends(get_db)):
    projects = (
        db.query(models.Project)
        .filter(models.Project.is_published.is_(True))
        .order_by(models.Project.sort_order.asc(), models.Project.id.desc())
        .all()
    )
    s = _settings(db)
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "projects": projects,
            "app_name": s.get("app_name", "AppsWire"),
            "app_subtitle": s.get("app_subtitle", "Applications · Tools · Experiments"),
        },
    )


@app.get("/instruction/{project_id}", response_class=HTMLResponse)
async def instruction(
    request: Request, project_id: int, db: Session = Depends(get_db)
):
    project = (
        db.query(models.Project).filter(models.Project.id == project_id).first()
    )
    if not project or not project.instruction_md:
        raise HTTPException(status_code=404)
    content_html = md.markdown(
        project.instruction_md,
        extensions=["tables", "fenced_code", "toc", "sane_lists"],
    )
    s = _settings(db)
    return templates.TemplateResponse(
        request,
        "instruction.html",
        {
            "project": project,
            "content_html": content_html,
            "app_name": s.get("app_name", "AppsWire"),
        },
    )


@app.get("/download/{action_id}")
async def download_file(action_id: int, db: Session = Depends(get_db)):
    action = (
        db.query(models.Action).filter(models.Action.id == action_id).first()
    )
    if not action or action.kind != "download" or not action.file_path:
        raise HTTPException(status_code=404)
    try:
        file_path = fstore.resolve_safe(action.file_path)
    except ValueError:
        raise HTTPException(status_code=404)
    if not file_path.exists():
        raise HTTPException(status_code=404)
    return FileResponse(
        path=str(file_path),
        filename=file_path.name,
        media_type="application/octet-stream",
    )


# ── admin routes ──────────────────────────────────────────────────────────────

@app.get("/admin", response_class=HTMLResponse)
async def admin_get(
    request: Request,
    edit: Optional[int] = None,
    db: Session = Depends(get_db),
):
    s = _settings(db)
    ctx: dict = {"app_name": s.get("app_name", "AppsWire")}

    admin_user = auth.get_admin(db)
    if not admin_user:
        return templates.TemplateResponse(request, "admin_setup.html", ctx)

    uid = _session_uid(request)
    if not uid:
        return templates.TemplateResponse(request, "admin_login.html", ctx)

    projects = (
        db.query(models.Project)
        .order_by(models.Project.sort_order.asc(), models.Project.id.desc())
        .all()
    )
    edit_project_json = "null"
    if edit:
        ep = db.query(models.Project).filter(models.Project.id == edit).first()
        if ep:
            edit_project_json = json.dumps(_project_to_dict(ep))

    return templates.TemplateResponse(
        request,
        "admin_dashboard.html",
        {
            **ctx,
            "projects": projects,
            "edit_project_json": edit_project_json,
            "app_name": s.get("app_name", "AppsWire"),
            "app_subtitle": s.get("app_subtitle", "Applications · Tools · Experiments"),
        },
    )


@app.post("/admin/setup")
async def admin_setup(request: Request, db: Session = Depends(get_db)):
    s = _settings(db)
    ctx: dict = {"app_name": s.get("app_name", "AppsWire")}

    if auth.get_admin(db):
        return RedirectResponse("/admin", status_code=302)

    form = await request.form()
    password = str(form.get("password", "")).strip()
    password_confirm = str(form.get("password_confirm", "")).strip()

    errors = []
    if not password or len(password) < 8:
        errors.append("Пароль должен содержать не менее 8 символов.")
    if password and password != password_confirm:
        errors.append("Пароли не совпадают.")

    if errors:
        return templates.TemplateResponse(
            request, "admin_setup.html", {**ctx, "errors": errors}
        )

    user = auth.create_admin(db, password)
    response = RedirectResponse("/admin", status_code=302)
    auth.set_session(response, user.id, _secret())
    return response


@app.post("/admin/login")
async def admin_login(request: Request, db: Session = Depends(get_db)):
    s = _settings(db)
    ctx: dict = {"app_name": s.get("app_name", "AppsWire")}

    admin_user = auth.get_admin(db)
    if not admin_user:
        return RedirectResponse("/admin", status_code=302)

    form = await request.form()
    password = str(form.get("password", ""))

    if not auth.verify_password(password, admin_user.password_hash):
        return templates.TemplateResponse(
            request, "admin_login.html", {**ctx, "error": "Неверный пароль."}
        )

    response = RedirectResponse("/admin", status_code=302)
    auth.set_session(response, admin_user.id, _secret())
    return response


@app.get("/admin/logout")
async def admin_logout(request: Request):
    response = RedirectResponse("/admin", status_code=302)
    auth.clear_session(response)
    return response


@app.post("/admin/save")
async def admin_save(request: Request, db: Session = Depends(get_db)):
    uid = _session_uid(request)
    if not uid:
        return RedirectResponse("/admin", status_code=302)

    form = await request.form()

    project_id = int(form.get("project_id") or 0)
    title = str(form.get("title") or "").strip()
    description = str(form.get("description") or "").strip()
    version = str(form.get("version") or "1.0.0").strip() or "1.0.0"
    is_published = form.get("is_published") in ("on", "true", "1")
    sort_order = int(form.get("sort_order") or 0)
    image_mode = str(form.get("image_mode") or "none")
    image_url_input = str(form.get("image_url_input") or "").strip()
    instruction_md = str(form.get("instruction_md") or "").strip()
    primary_index = int(form.get("primary_index") or -1)

    if not title:
        return RedirectResponse("/admin", status_code=302)

    # ── create / update project ───────────────────────────────────────────────
    if project_id == 0:
        project = models.Project(
            title=title,
            description=description,
            version=version,
            is_published=is_published,
            sort_order=sort_order,
            instruction_md=instruction_md or None,
        )
        db.add(project)
        db.flush()
    else:
        project = (
            db.query(models.Project).filter(models.Project.id == project_id).first()
        )
        if not project:
            raise HTTPException(status_code=404)
        project.title = title
        project.description = description
        project.version = version
        project.is_published = is_published
        project.sort_order = sort_order
        project.instruction_md = instruction_md or None

    # ── image ─────────────────────────────────────────────────────────────────
    if image_mode == "none":
        project.image_url = None
        project.image_path = None
    elif image_mode == "url":
        project.image_url = image_url_input or None
        project.image_path = None
    elif image_mode == "upload":
        image_file = form.get("image_file")
        if hasattr(image_file, "filename") and image_file.filename:
            try:
                rel = fstore.save_project_image(project.id, image_file)
                project.image_path = rel
                project.image_url = None
            except ValueError:
                pass
        # else: keep existing image_path

    db.flush()

    # ── actions ───────────────────────────────────────────────────────────────
    for a in list(project.actions):
        db.delete(a)
    db.flush()

    action_kinds = form.getlist("action_kind[]")
    action_labels = form.getlist("action_label[]")
    action_urls = form.getlist("action_url[]")
    action_existing_files = form.getlist("action_existing_file[]")
    action_clear_files = set(form.getlist("action_clear_file"))

    for i, kind in enumerate(action_kinds):
        label = (action_labels[i] if i < len(action_labels) else "").strip() or kind
        url_val = (action_urls[i] if i < len(action_urls) else "").strip()
        existing_file = (
            action_existing_files[i] if i < len(action_existing_files) else ""
        ).strip()

        action = models.Action(
            project_id=project.id,
            kind=kind,
            label=label,
            sort_order=i,
            is_primary=(i == primary_index),
        )

        if kind == "link":
            action.url = url_val or None

        elif kind == "download":
            clear = str(i) in action_clear_files
            uploaded = form.get(f"action_file_{i}")
            has_upload = hasattr(uploaded, "filename") and uploaded.filename

            if has_upload:
                try:
                    rel = fstore.save_project_file(project.id, uploaded)
                    action.file_path = rel
                except Exception:
                    if not clear:
                        action.file_path = existing_file or None
            elif clear:
                action.file_path = None
            else:
                action.file_path = existing_file or None

        db.add(action)

    db.commit()
    return RedirectResponse(f"/admin?edit={project.id}", status_code=302)


@app.post("/admin/delete/{project_id}")
async def admin_delete(
    request: Request, project_id: int, db: Session = Depends(get_db)
):
    uid = _session_uid(request)
    if not uid:
        return RedirectResponse("/admin", status_code=302)

    project = (
        db.query(models.Project).filter(models.Project.id == project_id).first()
    )
    if project:
        fstore.delete_project_storage(project_id)
        db.delete(project)
        db.commit()
    return RedirectResponse("/admin", status_code=302)


@app.post("/admin/settings")
async def admin_settings_save(request: Request, db: Session = Depends(get_db)):
    uid = _session_uid(request)
    if not uid:
        return RedirectResponse("/admin", status_code=302)

    form = await request.form()
    app_name = str(form.get("app_name") or "AppsWire").strip() or "AppsWire"
    app_subtitle = str(form.get("app_subtitle") or "").strip()

    for key, value in [("app_name", app_name), ("app_subtitle", app_subtitle)]:
        setting = db.query(models.Setting).filter(models.Setting.key == key).first()
        if setting:
            setting.value = value
        else:
            db.add(models.Setting(key=key, value=value))
    db.commit()
    return RedirectResponse("/admin", status_code=302)
