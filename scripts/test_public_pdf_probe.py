import io
import socket
import ssl
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import Mock
from public_pdf_probe import (
    TARGETS, RestrictedRedirect, allowed_url, check_pdf_signature, classify_error, fetch_one,
)

class Response(io.BytesIO):
    def __init__(self, data, content_type="application/pdf", reported=None):
        super().__init__(data)
        self.headers = {
            "Content-Type": content_type,
            "Content-Length": str(len(data) if reported is None else reported),
        }
    def getcode(self):
        return 200
    def geturl(self):
        return TARGETS[0]["url"]

class ProbeTests(unittest.TestCase):
    def test_allowed_https_only(self):
        self.assertTrue(allowed_url(TARGETS[0]["url"]))
        for url in ("http://www.ice.go.kr/a", "https://www.ice.go.kr.evil.example/a",
                    "https://user@www.ice.go.kr/a", "https://www.ice.go.kr:8443/a"):
            self.assertFalse(allowed_url(url))
    def test_dns_classification(self):
        self.assertEqual(classify_error(urllib.error.URLError(socket.gaierror(-3, "DNS"))),
                         "DNS_ERROR")
    def test_tls_classification(self):
        self.assertEqual(classify_error(urllib.error.URLError(
            ssl.SSLCertVerificationError(1, "bad cert"))), "TLS_CERTIFICATE_ERROR")
    def test_http_classification(self):
        exc = urllib.error.HTTPError(TARGETS[0]["url"], 403, "Forbidden", {}, None)
        self.assertEqual(classify_error(exc), "HTTP_403_PERMISSION_OR_POLICY")
    def test_successful_byte_preservation(self):
        data = b"%PDF-1.7\nsynthetic-test-data\n%%EOF\n"
        with tempfile.TemporaryDirectory() as tmp:
            op = Mock()
            op.open.return_value = Response(data)
            r = fetch_one(TARGETS[0], Path(tmp), op)
            self.assertEqual(r["status"], "saved")
            self.assertEqual((Path(tmp) / TARGETS[0]["filename"]).read_bytes(), data)
            self.assertEqual(r["bytes"], len(data))
    def test_reject_html_and_delete_partial(self):
        with tempfile.TemporaryDirectory() as tmp:
            op = Mock()
            op.open.return_value = Response(b"<html>Access denied</html>", "text/html")
            r = fetch_one(TARGETS[0], Path(tmp), op)
            self.assertEqual(r["status"], "failed")
            self.assertEqual(list(Path(tmp).iterdir()), [])
    def test_reject_oversize(self):
        with tempfile.TemporaryDirectory() as tmp:
            op = Mock()
            op.open.return_value = Response(b"x", reported=TARGETS[0]["limit"]+1)
            r = fetch_one(TARGETS[0], Path(tmp), op)
            self.assertEqual(r["status"], "failed")
    def test_incomplete_response(self):
        with tempfile.TemporaryDirectory() as tmp:
            op = Mock()
            data = b"%PDF-1.7\nsynthetic\n%%EOF"
            op.open.return_value = Response(data, reported=len(data)+3)
            self.assertEqual(fetch_one(TARGETS[0], Path(tmp), op)["status"], "failed")
    def test_redirect_policy(self):
        with self.assertRaises(ValueError):
            RestrictedRedirect().redirect_request(None, None, 302, "", {}, "https://example.com/x")
    def test_missing_eof(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)/"bad.pdf"
            p.write_bytes(b"%PDF-1.7\nmissing end")
            with self.assertRaises(ValueError):
                check_pdf_signature(p)

if __name__ == "__main__":
    unittest.main()
