import { execFileSync } from 'node:child_process';
import type { AppMode } from '../src/config/app-mode';
import { capabilityVersion } from '../src/config/app-mode';

export function releaseMetadata(appMode: AppMode) {
  let head: string | null = null;
  let dirty: boolean | null = null;
  try {
    head = execFileSync('git', ['rev-parse', 'HEAD'], { encoding: 'utf8' }).trim();
    dirty = Boolean(execFileSync('git', ['status', '--porcelain'], { encoding: 'utf8' }).trim());
  } catch {
    /* Source exports may have no Git metadata. Never invent a commit. */
  }
  const supplied = process.env.VERCEL_GIT_COMMIT_SHA || process.env.GITHUB_SHA;
  if (supplied && (!/^[a-f0-9]{40}$/i.test(supplied) || (head && supplied !== head)))
    throw new Error('Release commit does not match checked-out source.');
  return {
    schemaVersion: 1,
    mode: appMode === 'presentation' ? 'read-only-presentation' : appMode,
    appMode,
    capabilityVersion,
    ...(appMode === 'presentation' ? { sampleVersion: 'classsync-presentation-v1' } : {}),
    commit: supplied || head,
    uncommittedChanges: dirty,
  };
}
