// Temporary diagnostic observer; no test execution or assertion is changed.
module.exports = class StartupReporter {
  onTestRunStart(specifications) {
    process.stdout.write(`Diagnostic: ${specifications.length} modules selected\n`);
  }
  onTestModuleQueued(module) {
    process.stdout.write(`Queued: ${module.relativeModuleId}\n`);
  }
  onTestModuleCollected(module) {
    process.stdout.write(`Collected: ${module.relativeModuleId}\n`);
  }
  onTestModuleStart(module) {
    process.stdout.write(`Started: ${module.relativeModuleId}\n`);
  }
};
