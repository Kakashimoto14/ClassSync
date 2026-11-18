const path = require('node:path');

module.exports = function loadPlaywright() {
  const configured = process.env.CLASSSYNC_PLAYWRIGHT_MODULE;
  const moduleName = configured ? path.resolve(configured) : 'playwright';
  let resolved;
  try {
    resolved = require.resolve(moduleName);
  } catch (error) {
    if (error.code !== 'MODULE_NOT_FOUND') throw error;
    throw new Error(
      'Browser qualification requires Playwright. Make it locally resolvable or set ' +
        'CLASSSYNC_PLAYWRIGHT_MODULE to an existing Playwright installation.',
    );
  }
  return require(resolved);
};
