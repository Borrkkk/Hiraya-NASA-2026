import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';
import ts from 'typescript';

const exports = {};
vm.runInNewContext(ts.transpileModule(
  readFileSync(new URL('../src/lib/explore/observation-counts.ts', import.meta.url), 'utf8'),
  { compilerOptions: { module: ts.ModuleKind.CommonJS } },
).outputText, { exports });
const count = exports.countBandObservations;

test('one matching observation out of six available is 1/6', () => {
  const all = Array.from({ length: 6 }, (_, i) => ({ id: String(i), bands: ['starlight'] }));
  const result = count(all, [all[2]], 'starlight');
  assert.equal(result.selected, 1);
  assert.equal(result.total, 6);
});

test('counts use band coverage and selected time range, not six detectors', () => {
  const all = [
    { id: 'a', bands: ['starlight'] },
    { id: 'b', bands: ['starlight', 'hydrogen'] },
    { id: 'c', bands: ['hydrogen'] },
  ];
  assert.equal(count(all, [all[1]], 'starlight').total, 2);
  assert.equal(count(all, [all[1]], 'hydrogen').selected, 1);
  assert.equal(count(all, [all[1]], 'water-ice').total, 0);
  assert.equal(count(all, [], 'hydrogen').selected, 0);
});

test('missing band lists mean all bands, duplicate observations count once', () => {
  const all = [{ id: 'a' }, { id: 'a' }];
  assert.equal(count(all, all, 'starlight').selected, 1);
  assert.equal(count(all, all, 'starlight').total, 1);
});
