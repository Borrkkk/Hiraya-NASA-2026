import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';
import ts from 'typescript';

const exports = {};
vm.runInNewContext(ts.transpileModule(
  readFileSync(new URL('../src/lib/explore/window-selection.ts', import.meta.url), 'utf8'),
  { compilerOptions: { module: ts.ModuleKind.CommonJS } },
).outputText, { exports });
const select = (active, id, compatible) => Array.from(exports.toggleWindow(active, id, compatible));

test('isolated CO2 and CO windows can be reached while one window stays on', () => {
  assert.deepEqual(select(['starlight'], 'co2-ice', false), ['co2-ice']);
  assert.deepEqual(select(['co2-ice'], 'co-ice', false), ['co-ice']);
  assert.deepEqual(select(['co-ice'], 'co-ice', true), ['co-ice']);
});
test('compatible windows combine and can be removed individually', () => {
  assert.deepEqual(select(['starlight'], 'hydrogen', true), ['starlight', 'hydrogen']);
  assert.deepEqual(select(['starlight', 'hydrogen'], 'starlight', true), ['hydrogen']);
});
