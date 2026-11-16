"""Validate the actual distributable, including its ARM executable and contents."""
import hashlib
import io
import json
import struct
import subprocess
import tarfile
import os
import sys
import tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
IPK = ROOT / 'dist/org.streamlite.webos_1.3.0_all.ipk'
def minified(source):
    # Reproduce the locked LG packager's transformation, then enforce ES5 on
    # the bytes actually distributed. The packager minifies apps and services.
    program = """
const fs=require('fs');
const cliRequire=require('module').createRequire(require.resolve('@webos-tools/cli/package.json'));
const result=cliRequire('terser').minify(fs.readFileSync(0,'utf8'));
if(result.error) throw result.error;
require('acorn').parse(result.code,{ecmaVersion:5});
process.stdout.write(result.code);
"""
    return subprocess.check_output(['node', '-e', program], input=source.read_bytes(), cwd=ROOT)
assert IPK.stat().st_size < 512 * 1024, 'IPK exceeds the 512 KiB release budget'
archive = subprocess.check_output(['ar', 'p', str(IPK), 'data.tar.gz'])
with tarfile.open(fileobj=io.BytesIO(archive), mode='r:gz') as tar:
    files = {member.name.removeprefix('./'): member for member in tar.getmembers() if member.isfile()}
    app = 'usr/palm/applications/org.streamlite.webos/'
    service = 'usr/palm/services/org.streamlite.webos.service/'
    def data(name):
        return tar.extractfile(files[name]).read()
    manifest = json.loads(data(app + 'appinfo.json'))
    assert manifest['id'] == 'org.streamlite.webos' and manifest['version'] == '1.3.0'
    for filename in ['app.js', 'native.js', 'index.html', 'style.css']:
        source = ROOT / 'app' / filename
        expected = minified(source) if filename.endswith('.js') else source.read_bytes()
        assert data(app + filename) == expected, 'Stale app file: ' + filename
    assert data(app + 'config.js') == minified(ROOT / 'app/config.example.js'), 'Personal keys must never ship'
    assert json.loads(data(service + 'services.json'))['id'] == 'org.streamlite.webos.service'
    for filename in ['service.js', 'runner.js']:
        assert data(service + filename) == minified(ROOT / 'service' / filename)
    binary = data(service + 'streamlite-core')
    assert binary == (ROOT / 'native/target/armv7-unknown-linux-musleabihf/release/streamlite-core').read_bytes()
    assert binary[:7] == b'\x7fELF\x01\x01\x01', 'Expected ELF32 little-endian'
    assert struct.unpack_from('<H', binary, 18)[0] == 40, 'Expected ARM CPU'
    phoff = struct.unpack_from('<I', binary, 28)[0]
    phsize, phcount = struct.unpack_from('<HH', binary, 42)
    assert all(struct.unpack_from('<I', binary, phoff + i*phsize)[0] != 3 for i in range(phcount)), 'Binary must be static'
    assert files[service + 'streamlite-core'].mode & 0o111, 'Worker must be executable'
    assert len(binary) < 600 * 1024, 'Core exceeds 600 KiB release budget'
    assert data(app + 'LICENSE') == (ROOT / 'LICENSE').read_bytes()
    for notice in ['musl-1.2.3-COPYRIGHT', 'rust-COPYRIGHT', 'rust-LICENSE-MIT', 'dependencies.json']:
        assert data(service + 'licenses/' + notice), 'Missing notice: ' + notice
    if '--ui-test' in sys.argv:
        with tempfile.TemporaryDirectory(prefix='streamlite-ipk-') as temporary:
            for name in files:
                if name.startswith(app):
                    relative = Path(name.removeprefix(app))
                    assert len(relative.parts) == 1
                    (Path(temporary) / relative).write_bytes(data(name))
            environment = dict(os.environ, STREAMLITE_APP=temporary)
            subprocess.run([sys.executable, str(ROOT / 'tests/e2e_test.py'), '--native'],
                           env=environment, check=True, cwd=ROOT)
summary = {'ipk_bytes': IPK.stat().st_size, 'arm_core_bytes': len(binary),
           'arm_core_sha256': hashlib.sha256(binary).hexdigest(), 'ipk_sha256': hashlib.sha256(IPK.read_bytes()).hexdigest()}
(ROOT / 'dist/verification.json').write_text(json.dumps(summary, indent=2) + '\n')
print('PASS IPK: current source, static ARM, executable permissions, no API keys, licenses, size budgets')
print(json.dumps(summary, indent=2))
