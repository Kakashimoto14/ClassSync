import type { ReactNode } from 'react';
import '../layout/page.css';

export interface Column<Row> {
  header: string;
  /** Header content when it is a control rather than the header text. */
  head?: ReactNode;
  numeric?: boolean;
  className?: string;
  /** Leave the phone layout's row label out (selection and action columns). */
  unlabelled?: boolean;
  cell: (row: Row) => ReactNode;
}

/** Hairline table with right-aligned numbers that stacks into labelled rows on phones. */
export function DataTable<Row>({
  label,
  columns,
  rows,
  rowKey,
  className = '',
  scroll = false,
}: {
  label: string;
  columns: Column<Row>[];
  rows: Row[];
  rowKey: (row: Row, index: number) => string;
  className?: string;
  /** Cap the height of long tables; the region is then keyboard-scrollable. */
  scroll?: boolean;
}) {
  return (
    <div
      className={`data-table data-table--stack${scroll ? ' data-table--scroll' : ''}`}
      {...(scroll ? { role: 'region', 'aria-label': `${label} table`, tabIndex: 0 } : {})}
    >
      <table className={`table ${className}`.trim()} aria-label={label}>
        <thead>
          <tr>
            {columns.map((column) => (
              <th
                key={column.header}
                scope="col"
                className={column.className}
                data-numeric={column.numeric || undefined}
              >
                {column.head ?? column.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
            <tr key={rowKey(row, index)}>
              {columns.map((column) => (
                <td
                  key={column.header}
                  className={column.className}
                  data-label={column.unlabelled ? '' : column.header}
                  data-numeric={column.numeric || undefined}
                >
                  {column.cell(row)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
