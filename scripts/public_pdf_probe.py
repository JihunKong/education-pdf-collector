#!/usr/bin/env python3
"""Bounded public-PDF test for a dedicated GitHub repository with encrypted artifacts.
Python standard library only. No credentials, cookie import, DNS changes or TLS bypass.
The output PDF remains an unmodified source; signature checks are not full PDF validation.
"""
from __future__ import annotations

import hashlib
import json
import socket
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ALLOWED_HOSTS = {"www.ice.go.kr", "www.jne.go.kr", "www.moe.go.kr"}
MAX_PDF_BYTES = 20 * 1024 * 1024
MAX_HTML_BYTES = 2 * 1024 * 1024
TARGETS = [
    {
        "id": "sample_pdf",
        "url": "https://www.ice.go.kr/upload/ice/na/bbs_1630/2026/02/54805c6beb01532ef8ecb9b71a3155ed.pdf",
        "filename": "sample_2026_school_record_primary.pdf",
        "kind": "pdf",
        "limit": MAX_PDF_BYTES,
        "note": "Network test only; edition matching and full PDF validation are pending.",
    },
    {
        "id": "T001_source_page",
        "url": "https://www.jne.go.kr/open/na/ntt/selectNttInfo.do?mi=551&nttSn=5135663",
        "filename": "T001_source_page.html",
        "kind": "html",
        "limit": MAX_HTML_BYTES,
        "note": "Public source HTML for subsequent attachment-link analysis; not a PDF.",
    },
]

def allowed_url(url: str) -> bool:
    p = urllib.parse.urlsplit(url)
    try:
        port = p.port
    except ValueError:
        return False
    return (
        p.scheme == "https"
        and p.hostname in ALLOWED_HOSTS
        and port in (None, 443)
        and p.username is None
        and p.password is None
    )

class RestrictedRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not allowed_url(newurl):
            raise ValueError("Redirect outside the approved HTTPS hosts; stopped.")
        return super().redirect_request(req, fp, code, msg, headers, newurl)

def classify_error(exc: BaseException) -> str:
    if isinstance(exc, urllib.error.HTTPError):
        return {
            401: "HTTP_401_PERMISSION",
            403: "HTTP_403_PERMISSION_OR_POLICY",
            404: "HTTP_404_NOT_FOUND",
            429: "HTTP_429_RATE_LIMIT",
        }.get(exc.code, "HTTP_" + str(exc.code))
    cause = exc.reason if isinstance(exc, urllib.error.URLError) else exc
    if isinstance(cause, socket.gaierror):
        return "DNS_ERROR"
    if isinstance(cause, ssl.SSLCertVerificationError):
        return "TLS_CERTIFICATE_ERROR"
    if isinstance(cause, ssl.SSLError):
        return "TLS_ERROR"
    if isinstance(cause, (TimeoutError, socket.timeout)):
        return "TIMEOUT"
    if isinstance(exc, ValueError):
        return "VALIDATION_OR_POLICY_ERROR"
    if isinstance(cause, OSError):
        return "NETWORK_OR_IO_ERROR"
    return type(exc).__name__

def check_pdf_signature(path: Path) -> None:
    size = path.stat().st_size
    if size < 16:
        raise ValueError("Response too small to be a PDF.")
    with path.open("rb") as f:
        head = f.read(1024)
        f.seek(max(0, size - 4096))
        tail = f.read()
    if not head.startswith(b"%PDF-"):
        raise ValueError("Response is not a PDF; HTML/errors must not be stored as PDF.")
    if b"%%EOF" not in tail:
        raise ValueError("PDF end marker missing; possible incomplete response.")

def fetch_one(target: dict[str, Any], outdir: Path, opener=None) -> dict[str, Any]:
    started = time.monotonic()
    outdir.mkdir(parents=True, exist_ok=True)
    filename = target["filename"]
    if Path(filename).name != filename:
        raise ValueError("Filename must be a basename.")
    dst = outdir / filename
    part = dst.with_suffix(dst.suffix + ".part")
    record: dict[str, Any] = {
        "id": target["id"],
        "source_url": target["url"],
        "kind": target["kind"],
        "utc": datetime.now(timezone.utc).isoformat(),
        "status": "not_started",
        "note": target["note"],
        "tls_verification": True,
        "full_pdf_validation": "pending_in_receiving_environment",
        "redistribution_approval": "not_reviewed",
    }
    try:
        if not allowed_url(target["url"]):
            raise ValueError("Target not in the approved HTTPS host list.")
        if opener is None:
            opener = urllib.request.build_opener(
                RestrictedRedirect(),
                urllib.request.HTTPSHandler(context=ssl.create_default_context()),
            )
        req = urllib.request.Request(target["url"], headers={
            "User-Agent": "EducationPDFCollection/0.1 (bounded public document test)",
            "Accept": "application/pdf,text/html;q=0.8",
            "Accept-Encoding": "identity",
        })
        received = 0
        digest = hashlib.sha256()
        with opener.open(req, timeout=20) as response:
            record["http_status"] = response.getcode()
            record["final_url"] = response.geturl()
            if not allowed_url(record["final_url"]):
                raise ValueError("Unapproved final URL.")
            record["content_type"] = response.headers.get("Content-Type", "")
            content_length = response.headers.get("Content-Length")
            if content_length and content_length.isdigit():
                record["reported_bytes"] = int(content_length)
                if int(content_length) > target["limit"]:
                    raise ValueError("Content-Length exceeds size limit.")
            if record["http_status"] != 200:
                raise ValueError("Expected a full HTTP 200 response.")
            with part.open("wb") as f:
                while True:
                    if time.monotonic() - started > 75:
                        raise TimeoutError("Total file time budget exceeded.")
                    chunk = response.read(65536)
                    if not chunk:
                        break
                    received += len(chunk)
                    if received > target["limit"]:
                        raise ValueError("Streaming size limit exceeded.")
                    f.write(chunk)
                    digest.update(chunk)
        if not received:
            raise ValueError("Empty response.")
        if "reported_bytes" in record and record["reported_bytes"] != received:
            raise ValueError("Content-Length and received byte count differ.")
        if target["kind"] == "pdf":
            check_pdf_signature(part)
        else:
            if "html" not in record.get("content_type", "").lower():
                raise ValueError("Source-page response is not declared HTML.")
        part.replace(dst)
        record.update({
            "status": "saved",
            "filename": filename,
            "bytes": received,
            "sha256": digest.hexdigest(),
        })
    except Exception as exc:
        part.unlink(missing_ok=True)
        record.update({
            "status": "failed",
            "error_type": classify_error(exc),
            "error": str(exc)[:500],
        })
    record["elapsed_seconds"] = round(time.monotonic() - started, 3)
    return record

def main() -> int:
    outdir = Path("output")
    outdir.mkdir(exist_ok=True)
    results = []
    for target in TARGETS:
        result = fetch_one(target, outdir)
        results.append(result)
        (outdir / "probe_results.json").write_text(
            json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(json.dumps({
            "id": result["id"], "status": result["status"],
            "error_type": result.get("error_type"),
            "bytes": result.get("bytes"),
        }, ensure_ascii=False), flush=True)
        time.sleep(1)
    success = results[0]["status"] == "saved"
    summary = (
        "# Public PDF transport test\n\n"
        f"Sample PDF saved: {success}\n\n"
        "The sample is not counted as a fulfilled request yet. "
        "Full PDF parsing, cover/edition checks and redistribution review are pending.\n"
    )
    (outdir / "SUMMARY.md").write_text(summary, encoding="utf-8")
    return 0 if success else 2

if __name__ == "__main__":
    sys.exit(main())
