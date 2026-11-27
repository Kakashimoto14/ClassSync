// Fail when the web app's main entry chunk exceeds its raw-size budget.
// Usage (after `npm run build`): node scripts/check_bundle_budget.mjs [distDir] [maxBytes]
import { readFileSync, statSync } from 'node:fs';
import { join, resolve } from 'node:path';

const dist = resolve(process.argv[2] ?? 'apps/web/dist');
// 99 KiB. Route pages, setup filters and the timetable workspace load as lazy chunks.
const budget = Number(process.argv[3] ?? 101_376);

const html = readFileSync(join(dist, 'index.html'), 'utf8');
const entries = [...html.matchAll(/<script[^>]*type="module"[^>]*src="([^"]+)"/g)].map((m) => m[1]);
if (entries.length !== 1) {
  console.error(`Expected one module entry script in index.html, found ${entries.length}.`);
  process.exit(1);
}
const file = join(dist, entries[0].replace(/^\//, ''));
const size = statSync(file).size;
const verdict = size <= budget ? 'within' : 'OVER';
console.log(`Main entry ${entries[0]}: ${size} bytes raw (${verdict} budget of ${budget}).`);
process.exit(size <= budget ? 0 : 1);
