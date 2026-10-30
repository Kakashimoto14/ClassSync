const assert = require('node:assert/strict');
const test = require('node:test');
const { localEmulatorEnvironment, qualificationModule } = require('../auth_emulator_qualification.cjs');

test('owned emulator environment removes credentials and every inherited proxy spelling', () => {
  const source = { PATH: 'retained', HTTP_PROXY: 'sentinel', https_proxy: 'sentinel',
    ALL_PROXY: 'sentinel', no_proxy: 'sentinel', Firebase_token: 'sentinel',
    GOOGLE_APPLICATION_CREDENTIALS: 'sentinel', GCLOUD_PROJECT: 'sentinel' };
  const child = localEmulatorEnvironment(source, 'owned-root');
  assert.equal(child.PATH, 'retained');
  assert.equal(child.NO_PROXY, '*');
  assert.equal(child.XDG_CONFIG_HOME, 'owned-root');
  assert.equal(child.APPDATA, 'owned-root');
  assert.equal(JSON.stringify(child).includes('sentinel'), false);
  assert.equal(source.HTTP_PROXY, 'sentinel');
});

test('owned emulator entry selects only fixed qualification modules and exact flags', () => {
  const base = ['--tools-root', 'owned-tools', '--postgres-bin', 'owned-bin', '--output', 'new.json'];
  const expected = {
    '--browser': 'scripts.postgres_web_session_qualification',
    '--academic': 'scripts.postgres_academic_provider_qualification',
    '--scheduling': 'scripts.postgres_scheduling_provider_qualification',
    '--publication': 'scripts.postgres_publication_provider_qualification',
    '--student-browser': 'scripts.postgres_student_experience_qualification',
  };
  assert.equal(qualificationModule(base), 'scripts.postgres_emulator_qualification');
  for (const [flag, name] of Object.entries(expected)) {
    assert.equal(qualificationModule([...base, flag]), name);
  }
  for (const args of [
    [...base, '--script=arbitrary'], [...base, '--browser', '--scheduling'],
    ['--wrong', ...base.slice(1)], base.slice(0, 5), [...base, '--unknown'],
    [...base, '__proto__'], [...base, 'constructor'],
  ]) assert.throws(() => qualificationModule(args), /Explicit tools root/);
});
