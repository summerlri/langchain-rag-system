"""Claude 辅助命令使用的可重复 RAG 诊断、入库与冒烟测试工具。"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

BASE_URL = os.getenv("RAG_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
USERNAME = os.getenv("RAG_ADMIN_USERNAME", "admin")
PASSWORD = os.getenv("RAG_ADMIN_PASSWORD", "123456")


def request_json(path: str, *, method: str = "GET", token: str = "", data=None):
    body = json.dumps(data, ensure_ascii=False).encode("utf-8") if data is not None else None
    headers = {"Accept": "application/json"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(BASE_URL + path, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {detail}") from exc


def login() -> str:
    result = request_json(
        "/api/auth/login",
        method="POST",
        data={"username": USERNAME, "password": PASSWORD},
    )
    return result["access_token"]


def choose_kb(token: str, kb_id: str | None = None) -> str:
    knowledge_bases = request_json("/api/knowledge-bases", token=token)
    if kb_id:
        if not any(item["id"] == kb_id for item in knowledge_bases):
            raise RuntimeError(f"知识库不存在: {kb_id}")
        return kb_id
    if knowledge_bases:
        return knowledge_bases[0]["id"]
    created = request_json(
        "/api/knowledge-bases",
        method="POST",
        token=token,
        data={"name": "默认知识库", "description": "由 rag_ops.py 创建"},
    )
    return created["id"]


def upload_file(path: Path, kb_id: str, token: str) -> dict:
    boundary = f"----ragops-{uuid.uuid4().hex}"
    file_bytes = path.read_bytes()
    prefix = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{path.name}"\r\n'
        "Content-Type: application/octet-stream\r\n\r\n"
    ).encode("utf-8")
    body = prefix + file_bytes + f"\r\n--{boundary}--\r\n".encode("ascii")
    request = urllib.request.Request(
        f"{BASE_URL}/api/knowledge-bases/{kb_id}/documents",
        data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise RuntimeError(exc.read().decode("utf-8", errors="replace")) from exc


def command_ingest(args) -> int:
    path = Path(args.file).expanduser().resolve()
    if not path.is_file():
        raise RuntimeError(f"文件不存在: {path}")
    token = login()
    kb_id = choose_kb(token, args.kb_id)
    started = time.monotonic()
    document = upload_file(path, kb_id, token)
    doc_id = document["id"]
    deadline = time.monotonic() + args.timeout
    while time.monotonic() < deadline:
        documents = request_json(f"/api/knowledge-bases/{kb_id}/documents", token=token)
        current = next((item for item in documents if item["id"] == doc_id), None)
        if current and current["status"] in {"completed", "failed"}:
            elapsed = time.monotonic() - started
            print(json.dumps({"kb_id": kb_id, "elapsed_seconds": round(elapsed, 1), **current}, ensure_ascii=False, indent=2))
            return 0 if current["status"] == "completed" else 1
        time.sleep(2)
    raise RuntimeError(f"等待入库超过 {args.timeout} 秒")


def stream_chat(token: str, conversation_id: str, kb_id: str, question: str) -> list[dict]:
    body = json.dumps({"message": question, "kb_id": kb_id}, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        f"{BASE_URL}/api/chat/{conversation_id}",
        data=body,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method="POST",
    )
    events = []
    with urllib.request.urlopen(request, timeout=180) as response:
        for raw_line in response:
            line = raw_line.decode("utf-8").strip()
            if line.startswith("data: "):
                events.append(json.loads(line[6:]))
    return events


def command_smoke(_args) -> int:
    token = login()
    kb_id = choose_kb(token)
    cases = [
        ("iPhone 15 Pro Max 使用什么芯片？", ("A17 Pro",)),
        ("华为 Mate 60 Pro 有什么特色功能？", ("卫星", "HarmonyOS")),
        ("如何退货？", ("退货", "退换货")),
        ("那它需要什么条件？", tuple()),
    ]
    conversation = request_json(
        "/api/conversations",
        method="POST",
        token=token,
        data={"kb_id": kb_id, "title": "RAG 真实冒烟测试"},
    )
    passed = 0
    for index, (question, keywords) in enumerate(cases, 1):
        started = time.monotonic()
        events = stream_chat(token, conversation["id"], kb_id, question)
        errors = [event.get("content", "未知错误") for event in events if event.get("type") == "error"]
        answer = "".join(event.get("content", "") for event in events if event.get("type") == "token")
        has_sources = any(event.get("type") == "sources" and event.get("data") for event in events)
        completed = any(event.get("type") == "done" for event in events)
        rewritten = index < 4 or any(event.get("type") == "rewrite" for event in events)
        keyword_ok = not keywords or any(keyword in answer for keyword in keywords)
        ok = has_sources and completed and rewritten and keyword_ok
        passed += int(ok)
        print(f"{'PASS' if ok else 'FAIL'} | {time.monotonic() - started:.1f}s | {question}")
        if errors:
            print(f"  error: {errors[0]}")
        elif not ok:
            print(
                f"  checks: sources={has_sources}, done={completed}, "
                f"rewrite={rewritten}, keyword={keyword_ok}"
            )
    print(f"结果: {passed}/{len(cases)}")
    return 0 if passed == len(cases) else 1


def command_debug(args) -> int:
    failures = 0
    try:
        health = request_json("/api/health")
        print(f"PASS API: {health}")
    except Exception as exc:
        failures += 1
        print(f"FAIL API: {exc}")

    database = Path("data/rag.db")
    if database.exists():
        try:
            with sqlite3.connect(database) as connection:
                for table in ("users", "knowledge_bases", "documents", "conversations", "messages"):
                    count = connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                    print(f"PASS SQLite {table}: {count}")
                failed = connection.execute(
                    "SELECT filename, error_message FROM documents WHERE status='failed' LIMIT 5"
                ).fetchall()
                for filename, message in failed:
                    print(f"WARN failed document {filename}: {message or '无错误信息'}")
        except Exception as exc:
            failures += 1
            print(f"FAIL SQLite: {exc}")
    else:
        failures += 1
        print(f"FAIL SQLite: 文件不存在 {database}")

    try:
        import chromadb
        from backend.config import get_settings

        client = chromadb.PersistentClient(path=get_settings().chroma_persist_dir)
        collections = client.list_collections()
        print(f"PASS ChromaDB: {len(collections)} collections, {sum(item.count() for item in collections)} chunks")
    except Exception as exc:
        failures += 1
        print(f"FAIL ChromaDB: {exc}")

    cache = Path("data/cache")
    print(f"{'PASS' if cache.exists() else 'WARN'} cache: {cache}")

    if args.check_embedding:
        try:
            from backend.rag.embedding import BailianEmbeddings

            vector = BailianEmbeddings().embed_query("连通性测试")
            print(f"PASS Embedding: {len(vector)} dimensions")
        except Exception as exc:
            failures += 1
            print(f"FAIL Embedding: {exc}")
    return 0 if failures == 0 else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    debug = subparsers.add_parser("debug")
    debug.add_argument("--check-embedding", action="store_true")
    debug.set_defaults(handler=command_debug)
    ingest = subparsers.add_parser("ingest")
    ingest.add_argument("file")
    ingest.add_argument("--kb-id")
    ingest.add_argument("--timeout", type=int, default=120)
    ingest.set_defaults(handler=command_ingest)
    smoke = subparsers.add_parser("smoke")
    smoke.set_defaults(handler=command_smoke)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        return args.handler(args)
    except (OSError, RuntimeError, KeyError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
