import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';
import ts from 'typescript';

const compiled = ts.transpileModule(
  readFileSync(new URL('../src/lib/explore/frame-store.ts', import.meta.url), 'utf8'),
  { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } },
).outputText;

test('a newly visible frame moves ahead of queued background frames', async () => {
  const exports = {};
  vm.runInNewContext(compiled, { exports, AbortController, createImageBitmap: async () => ({ close() {} }) });
  const started = [];
  const pending = [];
  const api = { fetchFrame: (request) => {
    started.push(request.epochId);
    return new Promise((resolve) => pending.push(resolve));
  } };
  const store = new exports.FrameStore(api, 'area');
  for (const id of ['one', 'two', 'three', 'background', 'visible']) store.request(0, id, 'starlight');
  assert.deepEqual(started, ['one', 'two', 'three']);
  store.request(0, 'visible', 'starlight', true);
  pending.shift()(new Blob());
  await new Promise((resolve) => setImmediate(resolve));
  assert.deepEqual(started, ['one', 'two', 'three', 'visible']);
  store.dispose();
});
