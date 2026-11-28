import { Alert } from './Alert';
import { Button } from './Button';

/** Error banner with its own recovery action. Import from lazy pages only. */
export function InlineError({
  title,
  message,
  onRetry,
  retryLabel = 'Retry',
}: {
  title: string;
  message: string;
  onRetry: () => void;
  retryLabel?: string;
}) {
  return (
    <Alert
      tone="danger"
      title={title}
      action={
        <Button type="button" variant="secondary" onClick={onRetry}>
          {retryLabel}
        </Button>
      }
    >
      {message}
    </Alert>
  );
}
