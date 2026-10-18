import { useState } from 'react';

type LogoVariant = 'horizontal' | 'full' | 'symbol';
type LogoSurface = 'light' | 'dark';

export interface ClassSyncLogoProps {
  variant?: LogoVariant;
  surface?: LogoSurface;
  size?: 'small' | 'medium' | 'large';
  decorative?: boolean;
}

// Owner-supplied provisional raster derivatives, not an official SVG master.
// No dark master was supplied: the same unmodified artwork gets a light backing.
const assetRoot = `${import.meta.env.BASE_URL}branding/classsync-logo-assets/`;
const provisionalAssets: Record<LogoVariant, { file: string; width: number; height: number }> = {
  horizontal: { file: 'classsync-horizontal-light.png', width: 1100, height: 295 },
  full: { file: 'classsync-full-light.png', width: 1100, height: 310 },
  symbol: { file: 'classsync-ribbon-mark.png', width: 1024, height: 1024 },
};

export function ClassSyncLogo({
  variant = 'horizontal',
  surface = 'light',
  size = 'medium',
  decorative = false,
}: ClassSyncLogoProps) {
  const asset = provisionalAssets[variant];
  const source = assetRoot + asset.file;
  const [failedSource, setFailedSource] = useState<string | null>(null);
  const failed = failedSource === source;
  return (
    <span
      className={`classsync-logo classsync-logo--${size} classsync-logo--${surface}`}
      data-logo-variant={variant}
      data-logo-asset={failed ? 'fallback' : 'provisional-raster'}
      aria-hidden={decorative || undefined}
    >
      {!failed ? (
        <picture>
          {variant === 'full' && (
            <source
              media="(min-width: 1280px)"
              srcSet={source}
              width={asset.width}
              height={asset.height}
            />
          )}
          <img
            src={variant === 'full' ? assetRoot + provisionalAssets.horizontal.file : source}
            width={asset.width}
            height={variant === 'full' ? provisionalAssets.horizontal.height : asset.height}
            alt={decorative ? '' : 'ClassSync'}
            onError={() => setFailedSource(source)}
          />
        </picture>
      ) : (
        // Product-name text is deliberately not a reconstruction of the wordmark.
        <span className="classsync-logo__name">ClassSync</span>
      )}
      {variant === 'full' && failed && (
        <span className="classsync-logo__tagline">Smarter Classrooms Together</span>
      )}
    </span>
  );
}
