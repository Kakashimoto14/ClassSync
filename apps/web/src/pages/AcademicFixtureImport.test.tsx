import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, expect, it, vi } from 'vitest';
import { AcademicFixtureImport } from './AcademicFixtureImport';
afterEach(() => vi.unstubAllGlobals());
it('requires deliberate review and import, and never reports a rejected import as successful', async () => {
  const fetcher = vi
    .fn()
    .mockResolvedValue(
      new Response(JSON.stringify({ error: { message: 'Calendar dates need review' } }), {
        status: 422,
        headers: { 'content-type': 'application/json' },
      }),
    );
  vi.stubGlobal('fetch', fetcher);
  render(
    <MemoryRouter>
      <AcademicFixtureImport />
    </MemoryRouter>,
  );
  fireEvent.click(screen.getByText('Sample Academic Scenario'));
  fireEvent.click(screen.getByRole('button', { name: 'Review sample setup' }));
  expect(fetcher).not.toHaveBeenCalled();
  expect(screen.getByRole('region', { name: 'Review sample setup' })).toHaveTextContent('BSIT');
  fireEvent.click(screen.getByRole('button', { name: 'Import sample period' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('Calendar dates need review');
  expect(fetcher).toHaveBeenCalledTimes(1);
  const body = JSON.parse(fetcher.mock.calls[0][1].body);
  expect(body.program_ids).toEqual(['bsit']);
  expect(body.year_levels).toEqual([3]);
  expect(body.section_letters).toEqual(['A']);
});
