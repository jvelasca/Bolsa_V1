import assert from 'node:assert/strict';
import { test } from 'node:test';
import { join } from 'node:path';
import { probePython, projectVenvPython, readPyvenvHome } from './python.mjs';

test('readPyvenvHome extrae el intérprete base de un pyvenv.cfg de uv', () => {
  const cfg = [
    'home = C:\\Users\\josea\\AppData\\Roaming\\uv\\python\\cpython-3.12-windows-x86_64-none',
    'implementation = CPython',
    'uv = 0.12.3',
    'version_info = 3.12',
    'include-system-site-packages = false',
    '',
  ].join('\n');
  assert.equal(
    readPyvenvHome(cfg),
    'C:\\Users\\josea\\AppData\\Roaming\\uv\\python\\cpython-3.12-windows-x86_64-none',
  );
});

test('readPyvenvHome tolera entradas ausentes o no textuales', () => {
  assert.equal(readPyvenvHome('implementation = CPython'), null);
  assert.equal(readPyvenvHome(''), null);
  assert.equal(readPyvenvHome(undefined), null);
});

test('probePython marca como no ejecutable un binario inexistente', () => {
  const probe = probePython(join(process.cwd(), '__no_existe_python__.exe'));
  assert.equal(probe.ok, false);
  assert.ok(probe.code, 'debe informar un código de error');
});

test('probePython acepta un intérprete lanzable (el de la venv o el de PATH)', () => {
  const probe = probePython(projectVenvPython());
  if (!probe.ok) return; // entorno sin venv: nada que comprobar
  assert.match(probe.detail, /Python \d+\.\d+/);
});
