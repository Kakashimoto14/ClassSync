/** Public capability descriptions are not backend authorization. */
export type AppMode = 'presentation' | 'sandbox' | 'institutional';
export interface ModeInput {
  command: 'serve' | 'build';
  nodeEnv?: string;
  mode?: string;
  rolePreview?: string;
  presentationSample?: string;
  presentationTarget?: boolean;
}
export function resolveAppMode(input: ModeInput): AppMode {
  for (const value of [input.rolePreview, input.presentationSample]) {
    if (value !== undefined && value !== 'true' && value !== 'false')
      throw new Error('Legacy ClassSync flags must be exactly true or false.');
  }
  if (
    input.mode !== undefined &&
    !['presentation', 'sandbox', 'institutional'].includes(input.mode)
  )
    throw new Error('Invalid VITE_CLASSSYNC_MODE.');
  const flags = [input.rolePreview, input.presentationSample];
  let mode = input.mode as AppMode | undefined;
  if (input.presentationTarget) {
    if (mode && mode !== 'presentation')
      throw new Error('Presentation target contradicts app mode.');
    mode = 'presentation';
  }
  if (!mode) {
    if (input.command === 'serve' && input.nodeEnv !== 'production') mode = 'sandbox';
    else {
      if (flags.includes('true') && flags.includes('false'))
        throw new Error('Contradictory legacy ClassSync flags.');
      mode = flags.includes('true') ? 'presentation' : 'institutional';
    }
  }
  if (mode === 'presentation' && flags.includes('false'))
    throw new Error('Presentation requires preview and sample capabilities.');
  if (mode === 'institutional' && flags.includes('true'))
    throw new Error('Institutional mode cannot enable preview capabilities.');
  if (mode === 'sandbox' && (input.command === 'build' || input.nodeEnv === 'production'))
    throw new Error('Sandbox is restricted to the development server; never distributable.');
  return mode;
}

export const capabilityVersion = 1;
export function capabilitiesFor(mode: AppMode) {
  return Object.freeze({
    previewRoles: mode !== 'institutional',
    sample: mode !== 'institutional',
    sampleOnly: mode === 'presentation',
    connectedSandbox: mode === 'sandbox',
    liveRequests: mode === 'sandbox',
    description:
      mode === 'presentation'
        ? 'Read-only presentation. Generation, saving and publishing require a connected authorized backend.'
        : mode === 'sandbox'
          ? 'Local development sandbox. Every request remains subject to backend authorization.'
          : 'University identity and current permissions are required. Connected Student timetable reads are available through the authorized Gateway.',
  });
}
