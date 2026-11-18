import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, expect, it, vi } from 'vitest';
import { RegistrationScannerPage } from './RegistrationScannerPage';
import { UniversitySessionContext } from '../auth/university-session-context';
import type { UniversitySession } from '../auth/university-session';

const source = vi.hoisted(() => ({ request: vi.fn(), observe: vi.fn(), mode: 'institutional' }));
vi.mock('../config/runtime-config', () => ({
  get appMode() {
    return source.mode;
  },
}));
vi.mock('../auth/account-actions', () => ({
  accountRequest: source.request,
  observeAccount: source.observe,
}));
function field(value: string | number) {
  return {
    value,
    confidence: null,
    evidence: { page: 1, line: 1, excerpt: 'Invented academic field' },
  };
}
const scan = () => ({
  id: '11111111-1111-4111-8111-111111111111',
  method: 'digital-pdf',
  expires_at: new Date(Date.now() + 900_000).toISOString(),
  original_retained: false,
  fields: {
    academic_year: field('2026-2027'),
    semester: field('first'),
    student_identifier: field('SYN-OOI'),
    program: field('SYNTHETIC'),
    year_level: field(2),
  },
  courses: [
    { code: field('TESTIOI'), description: field('Invented seminar'), section: field('2') },
  ],
  warnings: [],
});
function page(state?: UniversitySession, path = '/student/registration-scanner') {
  return (
    <MemoryRouter initialEntries={[path]}>
      <UniversitySessionContext.Provider
        value={{
          available: true,
          state: state ?? {
            status: 'authorized',
            membership: {
              uid: 'student-a',
              tenant_id: 'synthetic',
              role: 'student',
              membership_revision: 1,
              student_id: 'SYN-001',
            },
          },
          refresh: vi.fn(),
          signOut: vi.fn(),
        }}
      >
        <RegistrationScannerPage />
      </UniversitySessionContext.Provider>
    </MemoryRouter>
  );
}
beforeEach(() => {
  vi.clearAllMocks();
  source.mode = 'institutional';
  source.observe.mockImplementation(async (listener) => {
    listener('student-a');
    return vi.fn();
  });
  source.request.mockImplementation(async (path, method) => {
    if (path === 'onboarding')
      return {
        email_verified: true,
        membership_state: null,
        claim_state: null,
        status: 'unlinked',
      };
    if (method === 'POST' && path === 'registration-documents') return scan();
    if (path.endsWith('/review'))
      return {
        status: 'matched',
        message: 'Matched using verified enrollment.',
        courses: [
          {
            code: 'TEST101',
            status: 'matched',
            offering: { section: { name: 'Synthetic approved section' } },
          },
        ],
        periods: [{ id: 'synthetic-period', title: 'Invented period', start: '2026-10-01' }],
      };
    return undefined;
  });
});

it('restores reviewed courses without restoring the student number or raw extraction', async () => {
  const restored = scan();
  const request = source.request.getMockImplementation();
  source.request.mockImplementation(async (path, method) => {
    if (path === `registration-documents/${restored.id}`) {
      return {
        ...restored,
        method: 'reviewed',
        fields: {},
        courses: [],
        reviewed: {
          academic_year: '2026-2027', semester: 'first', student_identifier: '',
          program: 'SYNTHETIC', year_level: 2,
          courses: [{ code: 'TEST101', description: 'Invented seminar', section: '2' }],
        },
      };
    }
    return request?.(path, method);
  });
  render(page(undefined, `/student/registration-scanner?scan=${restored.id}`));
  await screen.findByText(/Re-enter your student number/);
  expect(screen.getByLabelText('Student number')).toHaveValue('');
  expect(screen.getByLabelText('Course code')).toHaveValue('TEST101');
});

it('uploads privately, accepts corrections and links only a confirmed published result', async () => {
  render(page());
  const upload = await screen.findByLabelText('Choose a PDF or clear photo');
  fireEvent.change(upload, {
    target: {
      files: [new File(['invented UI fixture'], 'invented.pdf', { type: 'application/pdf' })],
    },
  });
  await screen.findByLabelText('Student number');
  expect(screen.getByLabelText('Student number')).toHaveValue('SYN-OOI');
  fireEvent.change(screen.getByLabelText('Student number'), { target: { value: 'SYN-001' } });
  fireEvent.change(screen.getByLabelText('Course code'), { target: { value: 'TEST101' } });
  fireEvent.click(screen.getByRole('button', { name: 'Find my classes' }));
  await screen.findByText('Matched using verified enrollment.');
  expect(source.request).toHaveBeenCalledWith(
    expect.stringMatching(/\/review$/),
    'POST',
    expect.objectContaining({
      student_identifier: 'SYN-001',
      courses: [{ code: 'TEST101', description: 'Invented seminar', section: '2' }],
    }),
    25_000,
  );
  expect(screen.getByRole('link', { name: 'View verified schedule' })).toHaveAttribute(
    'href',
    '/student/schedule?period=synthetic-period&date=2026-10-01',
  );
  fireEvent.change(screen.getByLabelText('Course code'), { target: { value: 'UNMATCHED' } });
  expect(screen.queryByRole('link', { name: 'View verified schedule' })).not.toBeInTheDocument();
});

it('clears private fields when the Firebase user changes', async () => {
  let identity!: (uid: string | null) => void;
  source.observe.mockImplementation(async (listener) => {
    identity = listener;
    listener('student-a');
    return vi.fn();
  });
  render(page());
  fireEvent.change(await screen.findByLabelText('Choose a PDF or clear photo'), {
    target: { files: [new File(['invented'], 'invented.pdf', { type: 'application/pdf' })] },
  });
  await screen.findByLabelText('Student number');
  source.request.mockImplementation(async (path) => {
    if (path === 'onboarding')
      return { email_verified: true, membership_state: null, claim_state: null };
    throw new Error('This scan is unavailable or expired.');
  });
  act(() => identity('student-b'));
  await waitFor(() =>
    expect(source.request.mock.calls.filter(([path]) => path === 'onboarding')).toHaveLength(2),
  );
  expect(screen.queryByLabelText('Student number')).not.toBeInTheDocument();
  expect(screen.queryByDisplayValue('SYN-OOI')).not.toBeInTheDocument();
});

it('displays a failed upload honestly and keeps manual entry available', async () => {
  source.request.mockImplementation(async (path) => {
    if (path === 'onboarding') return { email_verified: true, membership_state: null };
    throw new Error('This file could not be safely read.');
  });
  render(page());
  fireEvent.change(await screen.findByLabelText('Choose a PDF or clear photo'), {
    target: { files: [new File(['invalid'], 'bad.pdf', { type: 'application/pdf' })] },
  });
  await screen.findByRole('alert');
  expect(screen.getByRole('alert')).toHaveTextContent('could not be safely read');
  expect(screen.getByRole('button', { name: 'Enter courses manually' })).toBeEnabled();
  expect(screen.queryByRole('link', { name: 'View verified schedule' })).not.toBeInTheDocument();
});

it('deletes the server-side temporary review before clearing the form', async () => {
  render(page());
  fireEvent.change(await screen.findByLabelText('Choose a PDF or clear photo'), {
    target: { files: [new File(['invented'], 'invented.pdf', { type: 'application/pdf' })] },
  });
  await screen.findByLabelText('Student number');
  fireEvent.click(screen.getByRole('button', { name: 'Delete temporary scan' }));
  await waitFor(() =>
    expect(source.request).toHaveBeenCalledWith(
      'registration-documents/11111111-1111-4111-8111-111111111111',
      'DELETE',
    ),
  );
  expect(await screen.findByText('Your temporary scan was deleted.')).toBeInTheDocument();
  expect(screen.queryByLabelText('Student number')).not.toBeInTheDocument();
});

it.each(['checking', 'denied', 'offline'] as const)(
  'hides and clears published matches after Student authorization becomes %s',
  async (status) => {
    const view = render(page());
    fireEvent.change(await screen.findByLabelText('Choose a PDF or clear photo'), {
      target: { files: [new File(['invented'], 'invented.pdf', { type: 'application/pdf' })] },
    });
    await screen.findByLabelText('Student number');
    fireEvent.click(screen.getByRole('button', { name: 'Find my classes' }));
    await screen.findByRole('link', { name: 'View verified schedule' });
    view.rerender(page({ status }));
    expect(screen.queryByRole('link', { name: 'View verified schedule' })).not.toBeInTheDocument();
    expect(screen.queryByText('Matched using verified enrollment.')).not.toBeInTheDocument();
    view.rerender(page());
    expect(screen.queryByRole('link', { name: 'View verified schedule' })).not.toBeInTheDocument();
  },
);

it('discards an in-flight match across authorization loss and restoration', async () => {
  const existingRequest = source.request.getMockImplementation()!;
  let resolveReview!: (value: unknown) => void;
  source.request.mockImplementation((path, ...args) =>
    path.endsWith('/review')
      ? new Promise((resolve) => {
          resolveReview = resolve;
        })
      : existingRequest(path, ...args),
  );
  const view = render(page());
  fireEvent.change(await screen.findByLabelText('Choose a PDF or clear photo'), {
    target: { files: [new File(['invented'], 'invented.pdf', { type: 'application/pdf' })] },
  });
  await screen.findByLabelText('Student number');
  fireEvent.click(screen.getByRole('button', { name: 'Find my classes' }));
  await waitFor(() => expect(resolveReview).toBeTypeOf('function'));
  view.rerender(page({ status: 'checking' }));
  view.rerender(page());
  await act(async () => {
    resolveReview(await existingRequest('registration-documents/test/review'));
  });
  expect(screen.queryByRole('link', { name: 'View verified schedule' })).not.toBeInTheDocument();
  expect(screen.queryByText('Matched using verified enrollment.')).not.toBeInTheDocument();
});
