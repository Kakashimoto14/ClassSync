// @vitest-environment node
import { describe, expect, it } from 'vitest';
import { capabilitiesFor, resolveAppMode, type AppMode } from './app-mode';

const flags = [undefined, 'true', 'false'];
describe('operating mode exhaustive compatibility matrix', () => {
  for (const command of ['serve', 'build'] as const)
    for (const nodeEnv of [undefined, 'development', 'production'])
      for (const mode of [undefined, 'presentation', 'sandbox', 'institutional'] as const)
        for (const rolePreview of flags)
          for (const presentationSample of flags)
            for (const presentationTarget of [false, true]) {
              const input = {
                command,
                nodeEnv,
                mode,
                rolePreview,
                presentationSample,
                presentationTarget,
              };
              it(JSON.stringify(input), () => {
                const both = [rolePreview, presentationSample];
                const expected: AppMode = presentationTarget
                  ? 'presentation'
                  : (mode ??
                    (command === 'serve' && nodeEnv !== 'production'
                      ? 'sandbox'
                      : both.includes('true')
                        ? 'presentation'
                        : 'institutional'));
                const invalid =
                  (presentationTarget && mode !== undefined && mode !== 'presentation') ||
                  (expected === 'presentation' && both.includes('false')) ||
                  (expected === 'institutional' && both.includes('true')) ||
                  (expected === 'sandbox' && (command === 'build' || nodeEnv === 'production'));
                if (invalid) expect(() => resolveAppMode(input)).toThrow();
                else expect(resolveAppMode(input)).toBe(expected);
              });
            }
  it.each(['', 'TRUE', '1', ' false ', 'yes'])('rejects malformed flag %s', (flag) => {
    for (const key of ['rolePreview', 'presentationSample'])
      expect(() => resolveAppMode({ command: 'build', [key]: flag })).toThrow();
  });
  it.each(['', 'production', 'dev', 'Presentation'])('rejects unknown mode %s', (mode) => {
    expect(() => resolveAppMode({ command: 'build', mode })).toThrow();
  });
  it('capabilities never describe preview identity as institutional authorization', () => {
    expect(capabilitiesFor('institutional').previewRoles).toBe(false);
    expect(capabilitiesFor('institutional').liveRequests).toBe(false);
    expect(capabilitiesFor('presentation').liveRequests).toBe(false);
    expect(capabilitiesFor('sandbox').description).toMatch(/backend authorization/);
    expect(Object.isFrozen(capabilitiesFor('sandbox'))).toBe(true);
  });
});
