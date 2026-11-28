import { useContext, type ReactNode, type Ref } from 'react';
import { NestedPageHeading } from './page-heading-context';
import './page.css';

/** One h1 per Administrator page: title, short context and the page's actions. */
export function PageHeader({
  title,
  titleId,
  titleRef,
  back,
  meta,
  actions,
}: {
  title: string;
  titleId?: string;
  titleRef?: Ref<HTMLHeadingElement>;
  back?: ReactNode;
  meta?: ReactNode;
  actions?: ReactNode;
}) {
  const Heading = useContext(NestedPageHeading) ? 'h2' : 'h1';
  return (
    <header className="page-header">
      <div>
        {back}
        <Heading id={titleId} ref={titleRef} tabIndex={titleRef ? -1 : undefined}>
          {title}
        </Heading>
        {meta && <div className="page-header__meta">{meta}</div>}
      </div>
      {actions && <div className="page-header__actions">{actions}</div>}
    </header>
  );
}
