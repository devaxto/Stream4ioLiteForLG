"""Bundle the exact dependency notices from the locked Cargo dependency graph."""
import json
import subprocess
import sys
from pathlib import Path
root = Path(__file__).resolve().parents[1]
metadata = json.loads(subprocess.check_output([
    'cargo', 'metadata', '--locked', '--offline', '--format-version', '1',
    '--manifest-path', str(root / 'native/Cargo.toml')], cwd=root / 'native'))
destination = Path(sys.argv[1])
destination.mkdir(parents=True, exist_ok=True)
for notice in (root / 'native/licenses').iterdir():
    if notice.is_file():
        (destination / notice.name).write_bytes(notice.read_bytes())
notices = []
for package in metadata['packages']:
    if package['name'] == 'streamlite-core':
        continue
    source = Path(package['manifest_path']).parent
    notices.append({'name': package['name'], 'version': package['version'], 'license': package['license']})
    files = [p for p in source.iterdir() if p.is_file() and p.name.upper().startswith(('LICENSE', 'COPYING', 'UNLICENSE'))]
    if not files:
        raise SystemExit('Missing license: ' + package['name'])
    for file in files:
        (destination / f"{package['name']}-{package['version']}-{file.name}").write_bytes(file.read_bytes())
(destination / 'dependencies.json').write_text(json.dumps(notices, indent=2) + '\n')
# The static executable also incorporates the Rust standard library and musl.
sysroot = Path(subprocess.check_output(['rustc', '--print', 'sysroot'], text=True, cwd=root / 'native').strip())
for name in ['COPYRIGHT', 'LICENSE-APACHE', 'LICENSE-MIT']:
    file = sysroot / 'share/doc/rust' / name
    if not file.is_file():
        raise SystemExit('Missing Rust distribution notice: ' + name)
    (destination / ('rust-' + name)).write_bytes(file.read_bytes())
