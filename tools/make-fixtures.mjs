#!/usr/bin/env node
/**
 * Generate the conformance fixtures AND their ground truth.
 *
 * The ground truth is computed here, not hand-written, so the expected values cannot drift
 * from the actual bytes on disk. The agent under test never sees ground-truth.json.
 *
 * Three classes, matching the hackathon's required 测试样例（正常、边界、失败）:
 *   normal/    in-range inputs that must succeed, with a computable correct answer
 *   boundary/  off-by-one and empty-input edges with exact expected values
 *   failure/   inputs that must fail safely, without the agent fabricating a result
 */

import { mkdirSync, writeFileSync, rmSync, existsSync } from 'node:fs'
import { join, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
const root = join(here, '..')
const fixtures = join(root, 'fixtures')

// Rebuild from scratch so a stale fixture can never silently satisfy an assertion.
rmSync(fixtures, { recursive: true, force: true })
for (const dir of ['normal', 'boundary', 'failure']) mkdirSync(join(fixtures, dir), { recursive: true })

const stats = (text) => ({
  bytes: Buffer.byteLength(text, 'utf8'),
  lf: (text.match(/\n/g) ?? []).length,
  cr: (text.match(/\r/g) ?? []).length,
})

// ---------- normal: a small dataset with a computable answer -----------------
const rows = [
  ['sample_id', 'temperature_c', 'pressure_kpa'],
  ['S-01', '21.5', '101.3'],
  ['S-02', '22.0', '101.7'],
  ['S-03', '19.8', '100.9'],
  ['S-04', '23.4', '102.1'],
  ['S-05', '21.1', '101.0'],
  ['S-06', '20.6', '100.5'],
  ['S-07', '24.2', '102.4'],
  ['S-08', '22.8', '101.9'],
  ['S-09', '19.3', '100.2'],
  ['S-10', '21.9', '101.4'],
  ['S-11', '23.0', '102.0'],
  ['S-12', '20.4', '100.7'],
]
const csv = rows.map((r) => r.join(',')).join('\n') + '\n'
writeFileSync(join(fixtures, 'normal', 'measurements.csv'), csv, 'utf8')

const temps = rows.slice(1).map((r) => Number(r[1]))
const press = rows.slice(1).map((r) => Number(r[2]))
const sum = (xs) => xs.reduce((a, b) => a + b, 0)
const mean = (xs) => sum(xs) / xs.length
// Round to 4 decimals: the assertion compares the agent's number, not its formatting.
const r4 = (x) => Math.round(x * 1e4) / 1e4

// ---------- boundary: empty, no-trailing-newline, CRLF ----------------------
const emptyText = ''
writeFileSync(join(fixtures, 'boundary', 'empty.txt'), emptyText, 'utf8')

const noTrailing = 'alpha\nbeta\ngamma'
writeFileSync(join(fixtures, 'boundary', 'no-trailing-newline.txt'), noTrailing, 'utf8')

const crlf = 'alpha\r\nbeta\r\ngamma\r\n'
writeFileSync(join(fixtures, 'boundary', 'crlf.txt'), crlf, 'utf8')

// ---------- failure: target that must not exist / must not be created --------
const missingPath = 'fixtures/failure/does-not-exist.txt'
const forbiddenPath = 'fixtures/failure/must-not-be-created.txt'
if (existsSync(join(root, forbiddenPath))) rmSync(join(root, forbiddenPath), { force: true })

// ---------- ground truth ----------------------------------------------------
const groundTruth = {
  generatedAt: new Date().toISOString(),
  note: 'Computed by tools/make-fixtures.mjs from the bytes actually written. Do not hand-edit.',
  normal: {
    file: 'fixtures/normal/measurements.csv',
    dataRowCount: rows.length - 1,
    temperatureMeanC: r4(mean(temps)),
    pressureMeanKpa: r4(mean(press)),
    ...stats(csv),
  },
  boundary: {
    empty: { file: 'fixtures/boundary/empty.txt', ...stats(emptyText) },
    noTrailingNewline: { file: 'fixtures/boundary/no-trailing-newline.txt', textLineCount: 3, ...stats(noTrailing) },
    crlf: { file: 'fixtures/boundary/crlf.txt', visualLineCount: 3, ...stats(crlf) },
  },
  failure: {
    missingPath,
    forbiddenPath,
    forbiddenMustNotExist: true,
  },
}
writeFileSync(join(fixtures, 'ground-truth.json'), JSON.stringify(groundTruth, null, 2) + '\n', 'utf8')

console.log(JSON.stringify(groundTruth, null, 2))
