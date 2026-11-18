const assert = require('node:assert/strict');
const test = require('node:test');
const {
  localEmulatorEnvironment,
  qualificationModule,
  pinnedTools,
} = require('../auth_emulator_qualification.cjs');

test('owned emulator environment removes credentials and every inherited proxy spelling', () => {
  const source = {
    PATH: 'retained',
    HTTP_PROXY: 'sentinel',
    https_proxy: 'sentinel',
    ALL_PROXY: 'sentinel',
    no_proxy: 'sentinel',
    Firebase_token: 'sentinel',
    GOOGLE_APPLICATION_CREDENTIALS: 'sentinel',
    GCLOUD_PROJECT: 'sentinel',
    COURSE_CLOUD_ENABLED: 'sentinel',
    GEMINI_API_KEY: 'sentinel',
  };
  const child = localEmulatorEnvironment(source, 'owned-root');
  assert.equal(child.PATH, 'retained');
  assert.equal(child.NO_PROXY, '*');
  assert.equal(child.XDG_CONFIG_HOME, 'owned-root');
  assert.equal(child.APPDATA, 'owned-root');
  assert.equal(JSON.stringify(child).includes('sentinel'), false);
  assert.equal(source.HTTP_PROXY, 'sentinel');
});

test('owned emulator entry selects only fixed qualification modules and exact flags', () => {
  const base = [
    '--tools-root',
    'owned-tools',
    '--postgres-bin',
    'owned-bin',
    '--output',
    'new.json',
  ];
  const expected = {
    '--browser': 'scripts.postgres_web_session_qualification',
    '--academic': 'scripts.postgres_academic_provider_qualification',
    '--scheduling': 'scripts.postgres_scheduling_provider_qualification',
    '--publication': 'scripts.postgres_publication_provider_qualification',
    '--student-browser': 'scripts.postgres_student_experience_qualification',
    '--onboarding': 'scripts.postgres_onboarding_qualification',
    '--onboarding-browser': 'scripts.postgres_onboarding_browser_qualification',
    '--scanner-browser': 'scripts.postgres_registration_browser_qualification',
    '--connected-browser': 'scripts.postgres_connected_browser_qualification',
    '--postman': 'scripts.postgres_postman_qualification',
    '--firestore-slice': 'scripts.postgres_firestore_access_qualification',
  };
  assert.equal(qualificationModule(base), 'scripts.postgres_emulator_qualification');
  for (const [flag, name] of Object.entries(expected)) {
    assert.equal(qualificationModule([...base, flag]), name);
  }
  for (const args of [
    [...base, '--script=arbitrary'],
    [...base, '--browser', '--scheduling'],
    ['--wrong', ...base.slice(1)],
    base.slice(0, 5),
    [...base, '--unknown'],
    [...base, '__proto__'],
    [...base, 'constructor'],
  ])
    assert.throws(() => qualificationModule(args), /Explicit tools root/);
});

test('development uses only the reviewed complete Auth tool installation', () => {
  assert.equal(pinnedTools(require('node:path').join(__dirname, 'missing-emulator-tools')), false);
});
