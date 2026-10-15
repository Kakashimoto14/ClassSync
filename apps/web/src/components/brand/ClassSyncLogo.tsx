type LogoVariant = 'horizontal' | 'full' | 'symbol';
type LogoSurface = 'light' | 'dark';

export interface ClassSyncLogoProps {
  variant?: LogoVariant;
  surface?: LogoSurface;
  size?: 'small' | 'medium' | 'large';
  decorative?: boolean;
}

// Register only owner-verified ribbon exports here. The supplied presentation
// board and the prototype's approximate SVG are not production logo assets.
const approvedAssets: Partial<Record<`${LogoVariant}-${LogoSurface}`, string>> = {};

export function ClassSyncLogo({
  variant = 'horizontal',
  surface = 'light',
  size = 'medium',
  decorative = false,
}: ClassSyncLogoProps) {
  const source = approvedAssets[`${variant}-${surface}`];
  return (
    <span
      className={`classsync-logo classsync-logo--${size} classsync-logo--${surface}`}
      data-logo-variant={variant}
      data-logo-asset={source ? 'approved' : 'pending'}
      aria-hidden={decorative || undefined}
    >
      {source ? (
        <img src={source} alt={decorative ? '' : 'ClassSync'} />
      ) : (
        // Product-name text is deliberately not a reconstruction of the wordmark.
        <span className="classsync-logo__name">ClassSync</span>
      )}
      {variant === 'full' && !source && (
        <span className="classsync-logo__tagline">Smarter Classrooms Together</span>
      )}
    </span>
  );
}
