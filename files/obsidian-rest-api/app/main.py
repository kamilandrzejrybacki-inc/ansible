"""
Standalone Obsidian Local REST API
Implements the coddingtonbear/obsidian-local-rest-api protocol against
a directory of markdown files, without requiring the Obsidian desktop app.
"""
import os
import re
import shutil
import urllib.parse
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response
from fastapi.responses import JSONResponse, PlainTextResponse

app = FastAPI(title="Obsidian Local REST API (Standalone)", version="1.0.0")

VAULT_ROOT = Path(os.environ["VAULT_ROOT"])
API_KEY = os.environ["API_KEY"]


# ── Auth ──────────────────────────────────────────────────────────────────────

def _verify(authorization: Optional[str] = Header(None)) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail={"errorCode": 40100, "message": "Unauthorized"})
    token = authorization[7:]
    if token != API_KEY:
        raise HTTPException(status_code=401, detail={"errorCode": 40100, "message": "Unauthorized"})
    return token


def _safe_path(path: str) -> Path:
    """Resolve path inside vault, reject traversal attempts."""
    resolved = (VAULT_ROOT / path).resolve()
    if not str(resolved).startswith(str(VAULT_ROOT.resolve())):
        raise HTTPException(status_code=400, detail={"errorCode": 40000, "message": "Invalid path"})
    return resolved


# ── Status ────────────────────────────────────────────────────────────────────

@app.get("/")
async def status(authorization: Optional[str] = Header(None)):
    authenticated = bool(
        authorization
        and authorization.startswith("Bearer ")
        and authorization[7:] == API_KEY
    )
    return {
        "ok": "OK",
        "service": "Obsidian Local REST API",
        "authenticated": authenticated,
        "versions": {"self": "1.0.0", "obsidian": "standalone"},
    }


# ── Vault file listing ────────────────────────────────────────────────────────

def _list_dir_response(dirpath: Path) -> dict:
    if not dirpath.exists() or not dirpath.is_dir():
        raise HTTPException(status_code=404, detail={"errorCode": 40400, "message": "Directory not found"})
    files = []
    for item in sorted(dirpath.iterdir()):
        rel = str(item.relative_to(VAULT_ROOT))
        files.append(rel + "/" if item.is_dir() else rel)
    return {"files": files}


@app.get("/vault/")
async def list_vault_root(_auth=Depends(_verify)):
    return _list_dir_response(VAULT_ROOT)


@app.get("/vault/{path:path}")
async def get_vault_path(path: str, _auth=Depends(_verify)):
    full = _safe_path(path)
    if path.endswith("/") or full.is_dir():
        return _list_dir_response(full if full.is_dir() else _safe_path(path.rstrip("/")))
    if not full.exists():
        raise HTTPException(status_code=404, detail={"errorCode": 40400, "message": "File not found"})
    return PlainTextResponse(full.read_text(encoding="utf-8"))


# ── Vault file writes ─────────────────────────────────────────────────────────

@app.put("/vault/{path:path}")
async def put_file(path: str, request: Request, _auth=Depends(_verify)):
    full = _safe_path(path)
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_bytes(await request.body())
    return Response(status_code=204)


@app.post("/vault/{path:path}")
async def append_file(path: str, request: Request, _auth=Depends(_verify)):
    full = _safe_path(path)
    full.parent.mkdir(parents=True, exist_ok=True)
    body = await request.body()
    with open(full, "ab") as f:
        if full.exists() and full.stat().st_size > 0:
            f.write(b"\n")
        f.write(body)
    return Response(status_code=204)


@app.patch("/vault/{path:path}")
async def patch_file(path: str, request: Request, _auth=Depends(_verify)):
    full = _safe_path(path)
    if not full.exists():
        raise HTTPException(status_code=404, detail={"errorCode": 40400, "message": "File not found"})

    operation = request.headers.get("Operation", "append").lower()
    target_type = request.headers.get("Target-Type", "heading").lower()
    target = urllib.parse.unquote(request.headers.get("Target", ""))
    body = (await request.body()).decode("utf-8")

    text = full.read_text(encoding="utf-8")

    if target_type == "frontmatter":
        text = _patch_frontmatter(text, operation, target, body)
    elif target_type == "heading":
        text = _patch_heading(text, operation, target, body)
    else:
        # block reference — append/prepend near the block marker
        text = _patch_block(text, operation, target, body)

    full.write_text(text, encoding="utf-8")
    return Response(status_code=204)


@app.delete("/vault/{path:path}")
async def delete_file(path: str, _auth=Depends(_verify)):
    full = _safe_path(path)
    if not full.exists():
        raise HTTPException(status_code=404, detail={"errorCode": 40400, "message": "File not found"})
    if full.is_dir():
        shutil.rmtree(full)
    else:
        full.unlink()
    return Response(status_code=204)


# ── Search ────────────────────────────────────────────────────────────────────

@app.post("/search/simple/")
async def search_simple(query: str, contextLength: int = 100, _auth=Depends(_verify)):
    results = []
    q = query.lower()
    for md_file in sorted(VAULT_ROOT.rglob("*.md")):
        try:
            text = md_file.read_text(encoding="utf-8", errors="ignore")
            text_lower = text.lower()
            if q not in text_lower:
                continue
            matches = []
            start = 0
            while True:
                idx = text_lower.find(q, start)
                if idx == -1:
                    break
                ctx_start = max(0, idx - contextLength)
                ctx_end = min(len(text), idx + len(query) + contextLength)
                matches.append({
                    "context": text[ctx_start:ctx_end],
                    "match": {"start": idx - ctx_start, "end": idx - ctx_start + len(query)},
                })
                start = idx + 1
                if len(matches) >= 5:
                    break
            results.append({
                "filename": str(md_file.relative_to(VAULT_ROOT)),
                "score": 1.0,
                "matches": matches,
            })
        except Exception:
            pass
    return results


@app.post("/search/")
async def search_json(_auth=Depends(_verify)):
    # DQL / JSONLogic search — not implemented in standalone mode
    return []


# ── Periodic notes (stub) ─────────────────────────────────────────────────────

@app.get("/periodic/{period}/")
async def get_periodic_note(period: str, _auth=Depends(_verify)):
    raise HTTPException(
        status_code=404,
        detail={"errorCode": 40400, "message": "Periodic notes not supported in standalone mode"},
    )


@app.get("/periodic/{period}/recent")
async def get_recent_periodic_notes(period: str, _auth=Depends(_verify)):
    raise HTTPException(
        status_code=404,
        detail={"errorCode": 40400, "message": "Periodic notes not supported in standalone mode"},
    )


# ── PATCH helpers ─────────────────────────────────────────────────────────────

def _patch_frontmatter(text: str, operation: str, field: str, content: str) -> str:
    """Add/update/prepend a frontmatter field."""
    fm_match = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    if not fm_match:
        # No frontmatter — create it
        new_fm = f"---\n{field}: {content.strip()}\n---\n"
        return new_fm + text

    fm_block = fm_match.group(1)
    body_after = text[fm_match.end():]
    field_re = re.compile(rf"^({re.escape(field)}:\s*)(.*)$", re.MULTILINE)
    existing = field_re.search(fm_block)

    if existing:
        if operation == "replace":
            fm_block = field_re.sub(rf"\g<1>{content.strip()}", fm_block)
        elif operation == "prepend":
            fm_block = field_re.sub(rf"\g<1>{content.strip()} \g<2>", fm_block)
        else:  # append
            fm_block = field_re.sub(rf"\g<1>\g<2> {content.strip()}", fm_block)
    else:
        fm_block += f"\n{field}: {content.strip()}"

    return f"---\n{fm_block}\n---\n{body_after}"


def _find_heading_range(lines: list[str], heading_path: str) -> tuple[int, int]:
    """
    Find the line range [heading_line, end_exclusive) for a heading path like
    'Heading 1 > Subheading' or just 'Heading 1'.
    Returns (-1, -1) if not found.
    """
    parts = [p.strip() for p in heading_path.split(">")]
    target_depth = len(parts)
    target_title = parts[-1].lower()

    heading_re = re.compile(r"^(#{1,6})\s+(.+)$")
    found_line = -1
    found_level = -1

    for i, line in enumerate(lines):
        m = heading_re.match(line)
        if m:
            level = len(m.group(1))
            title = m.group(2).strip().lower()
            if level == target_depth and title == target_title:
                found_line = i
                found_level = level
                break

    if found_line == -1:
        return -1, -1

    # Find end: next heading at same or higher level
    end = len(lines)
    for i in range(found_line + 1, len(lines)):
        m = heading_re.match(lines[i])
        if m and len(m.group(1)) <= found_level:
            end = i
            break

    return found_line, end


def _patch_heading(text: str, operation: str, heading_path: str, content: str) -> str:
    lines = text.splitlines(keepends=True)
    start, end = _find_heading_range([l.rstrip("\n") for l in lines], heading_path)

    if start == -1:
        # Heading not found — append a new one
        if not text.endswith("\n"):
            text += "\n"
        depth = heading_path.count(">") + 1
        return text + f"\n{'#' * depth} {heading_path.split('>')[-1].strip()}\n\n{content}\n"

    if operation == "replace":
        heading_line = lines[start]
        new_block = heading_line + content + ("\n" if not content.endswith("\n") else "")
        lines[start:end] = [new_block]
    elif operation == "prepend":
        insert_at = start + 1
        lines.insert(insert_at, content + ("\n" if not content.endswith("\n") else ""))
    else:  # append
        insert_at = end
        lines.insert(insert_at, content + ("\n" if not content.endswith("\n") else ""))

    return "".join(lines)


def _patch_block(text: str, operation: str, block_id: str, content: str) -> str:
    """Patch content relative to a block reference (^blockid)."""
    block_id = block_id.lstrip("^")
    lines = text.splitlines(keepends=True)
    for i, line in enumerate(lines):
        if re.search(rf"\^{re.escape(block_id)}\s*$", line.rstrip("\n")):
            if operation == "prepend":
                lines.insert(i, content + ("\n" if not content.endswith("\n") else ""))
            elif operation == "replace":
                lines[i] = content + ("\n" if not content.endswith("\n") else "")
            else:  # append
                lines.insert(i + 1, content + ("\n" if not content.endswith("\n") else ""))
            return "".join(lines)

    # Block not found — fall back to appending to end of file
    if not text.endswith("\n"):
        text += "\n"
    return text + content + ("\n" if not content.endswith("\n") else "")
