"""Archive and encrypt results before placing them in public Actions artifacts.
Requires OpenSSL 3 with CMS AES-GCM support. No private key is present in CI.
"""
from __future__ import annotations
import hashlib
import subprocess
import tempfile
import zipfile
from pathlib import Path


def seal(source: Path, cert: Path, destination: Path) -> None:
    files = sorted(p for p in source.rglob('*') if p.is_file())
    if not files or any(p.is_symlink() for p in source.rglob('*')):
        raise ValueError('Missing output or unexpected symbolic link.')
    if sum(p.stat().st_size for p in files) > 30 * 1024 * 1024:
        raise ValueError('Preflight output exceeds 30 MiB.')
    destination.parent.mkdir(parents=True, exist_ok=True)
    part = destination.with_suffix('.part')
    try:
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / 'results.zip'
            with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as z:
                for p in files:
                    z.write(p, p.relative_to(source).as_posix())
            subprocess.run([
                'openssl', 'cms', '-encrypt', '-binary', '-aes-256-gcm',
                '-in', str(archive), '-out', str(part), '-outform', 'DER',
                '-recip', str(cert), '-keyopt', 'rsa_padding_mode:oaep',
                '-keyopt', 'rsa_oaep_md:sha256', '-keyopt', 'rsa_mgf1_md:sha256',
            ], check=True, capture_output=True, timeout=30)
            part.replace(destination)
        digest = hashlib.sha256(destination.read_bytes()).hexdigest()
        destination.with_suffix('.sha256').write_text(digest + '  ' + destination.name + '\n')
        print('Encrypted artifact created. No plaintext source files will be uploaded.')
    finally:
        part.unlink(missing_ok=True)


if __name__ == '__main__':
    seal(Path('output'), Path('keys/recipient_cert.pem'), Path('sealed/results.cms'))
