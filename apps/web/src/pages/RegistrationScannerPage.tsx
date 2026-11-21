import { useEffect, useRef, useState, type FormEvent } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { accountRequest, observeAccount, type OnboardingStatus } from '../auth/account-actions';
import { useUniversitySession } from '../auth/university-session-context';
import { appMode } from '../config/runtime-config';
import { Button } from '../components/ui/Button';
import { formatStudentNumber } from '../auth/student-number';
import './registration-scanner.css';

interface Evidence {
  value: string | number;
  confidence: number | null;
  evidence: { page: number; line: number; excerpt: string };
}
interface Course {
  code: string;
  description: string;
  section: string;
  sourceIndex?: number;
}
interface Scan {
  id: string;
  expires_at: string;
  method: string;
  original_retained: false;
  fields: Partial<
    Record<'academic_year' | 'semester' | 'student_identifier' | 'program' | 'year_level', Evidence>
  >;
  courses: Array<{ code: Evidence; description: Evidence; section: Evidence }>;
  warnings: string[];
  reviewed?: Omit<Review, 'year_level'> & { year_level: number | null };
}
interface Review {
  academic_year: string;
  semester: string;
  student_identifier: string;
  program: string;
  year_level: string;
  courses: Course[];
}
interface Match {
  status: string;
  message: string;
  courses: Array<{
    code: string;
    status: string;
    document_section: string;
    document_section_verified: boolean;
    offering: { section: { name: string } } | null;
  }>;
  periods?: Array<{ id: string; title: string; start: string | null }>;
}
const CDM_PROGRAMS = [
  'BSIT', 'BSCPE', 'BSED-SCI', 'BEED-GEN', 'BEED-ECED',
  'BTLED-ICT', 'TCP', 'BSBA-HRM', 'BSE',
];
const emptyReview = (): Review => ({
  academic_year: '',
  semester: '',
  student_identifier: '',
  program: '',
  year_level: '',
  courses: [{ code: '', description: '', section: '' }],
});
function reviewFrom(scan: Scan): Review {
  if (scan.reviewed)
    return {
      ...scan.reviewed,
      year_level: String(scan.reviewed.year_level ?? ''),
      courses: scan.reviewed.courses.map((course) => ({ ...course, sourceIndex: undefined })),
    };
  const value = (name: keyof Scan['fields']) => String(scan.fields[name]?.value ?? '');
  return {
    academic_year: value('academic_year'),
    semester: value('semester'),
    student_identifier: formatStudentNumber(value('student_identifier')),
    program: value('program'),
    year_level: value('year_level'),
    courses: scan.courses.length
      ? scan.courses.map((course, sourceIndex) => ({
          code: String(course.code.value),
          description: String(course.description.value),
          section: String(course.section.value),
          sourceIndex,
        }))
      : emptyReview().courses,
  };
}
export function RegistrationScannerPage() {
  const [uid, setUid] = useState<string | null | undefined>();
  useEffect(() => {
    if (appMode !== 'institutional') return;
    let closed = false;
    let stop: (() => void) | undefined;
    void observeAccount((next) => {
      if (!closed) setUid(next);
    })
      .then((unsubscribe) => {
        if (closed) unsubscribe();
        else stop = unsubscribe;
      })
      .catch(() => {
        if (!closed) setUid(null);
      });
    return () => {
      closed = true;
      stop?.();
    };
  }, []);
  if (appMode !== 'institutional' || uid === null)
    return (
      <section className="registration-scanner workspace-card">
        <h1>Scan your registration form</h1>
        <p>Sign in to your university account to privately review your registration form.</p>
        <Link className="button" to="/auth/login">
          Sign in
        </Link>
      </section>
    );
  if (!uid)
    return (
      <section className="registration-scanner workspace-card" role="status">
        Checking your account…
      </section>
    );
  return <PrivateScanner key={uid} />;
}

function PrivateScanner() {
  const session = useUniversitySession();
  const [params, setParams] = useSearchParams();
  const initialScan = useRef(params.get('scan'));
  const [account, setAccount] = useState<OnboardingStatus | null>(null);
  const [scan, setScan] = useState<Scan | null>(null);
  const [review, setReview] = useState<Review>(emptyReview);
  const [matchResult, setMatch] = useState<Match | null>(null);
  const authorizedStudent =
    session.state.status === 'authorized' && session.state.membership.role === 'student';
  const currentStudentAuthority = useRef({ active: authorizedStudent, generation: 0 });
  if (currentStudentAuthority.current.active !== authorizedStudent)
    currentStudentAuthority.current = {
      active: authorizedStudent,
      generation: currentStudentAuthority.current.generation + 1,
    };
  const match =
    authorizedStudent || matchResult?.status === 'pending-verification' ? matchResult : null;
  useEffect(() => {
    if (!authorizedStudent)
      setMatch((current) => (current?.status === 'pending-verification' ? current : null));
  }, [authorizedStudent]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [load, setLoad] = useState(0);
  const fileInput = useRef<HTMLInputElement>(null);
  const heading = useRef<HTMLHeadingElement>(null);
  const resultHeading = useRef<HTMLHeadingElement>(null);
  useEffect(() => {
    let closed = false;
    void accountRequest<OnboardingStatus>('onboarding')
      .then(async (next) => {
        if (closed) return;
        setAccount(next);
        if (initialScan.current && next.email_verified) {
          const restored = await accountRequest<Scan>(
            `registration-documents/${encodeURIComponent(initialScan.current)}`,
          );
          if (!closed) {
            setScan(restored);
            setReview(reviewFrom(restored));
          }
        }
      })
      .catch((issue) => {
        if (!closed)
          setError(issue instanceof Error ? issue.message : 'Account status is unavailable.');
      });
    return () => {
      closed = true;
    };
  }, [load]);
  useEffect(() => {
    if (!scan) return;
    const timer = setTimeout(
      () => {
        setScan(null);
        setReview(emptyReview());
        setMatch(null);
        setNotice('This temporary scan expired. Choose your form again or enter your courses.');
        setParams({}, { replace: true });
      },
      Math.max(0, Date.parse(scan.expires_at) - Date.now()),
    );
    return () => clearTimeout(timer);
  }, [scan, setParams]);
  const execute = async (work: () => Promise<void>) => {
    setBusy(true);
    setError('');
    setNotice('');
    try {
      await work();
    } catch (issue) {
      setError(
        issue instanceof Error
          ? issue.message
          : 'The request could not be confirmed. Please try again.',
      );
    } finally {
      setBusy(false);
    }
  };
  const begin = async (file?: File) => {
    await execute(async () => {
      if (file && file.size > 10_000_000) throw new Error('Choose a smaller PDF, JPEG or PNG.');
      let body: Blob | undefined = file;
      if (file && !file.type) {
        const extension = file.name.split('.').pop()?.toLowerCase();
        const mime =
          extension === 'pdf'
            ? 'application/pdf'
            : extension === 'png'
              ? 'image/png'
              : ['jpg', 'jpeg'].includes(extension ?? '')
                ? 'image/jpeg'
                : '';
        body = new Blob([file], { type: mime });
      }
      const next = await accountRequest<Scan>(
        file ? 'registration-documents' : 'registration-documents/manual',
        'POST',
        body,
        40_000,
      );
      initialScan.current = next.id;
      setScan(next);
      setReview(reviewFrom(next));
      setMatch(null);
      setParams({ scan: next.id }, { replace: true });
      requestAnimationFrame(() => heading.current?.focus());
    });
    if (fileInput.current) fileInput.current.value = '';
  };
  const edit = (patch: Partial<Review>) => {
    setReview((current) => ({ ...current, ...patch }));
    setMatch(null);
    setNotice('');
  };
  const editCourse = (index: number, patch: Partial<Course>) =>
    edit({
      courses: review.courses.map((course, i) => (i === index ? { ...course, ...patch } : course)),
    });
  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!scan) return;
    setMatch(null);
    const authorityGeneration = currentStudentAuthority.current.generation;
    void execute(async () => {
      const result = await accountRequest<Match>(
        `registration-documents/${scan.id}/review`,
        'POST',
        {
          ...review,
          courses: review.courses.map((course) => ({
            code: course.code,
            description: course.description,
            section: course.section,
          })),
          year_level: review.year_level ? Number(review.year_level) : null,
        },
        25_000,
      );
      if (
        currentStudentAuthority.current.generation === authorityGeneration &&
        (currentStudentAuthority.current.active || result.status === 'pending-verification')
      )
        setMatch(result);
      requestAnimationFrame(() => resultHeading.current?.focus());
    });
  };
  const erase = () => {
    if (!scan) return;
    void execute(async () => {
      await accountRequest(`registration-documents/${scan.id}`, 'DELETE');
      initialScan.current = null;
      setScan(null);
      setReview(emptyReview());
      setMatch(null);
      setParams({}, { replace: true });
      setNotice('Your temporary scan was deleted.');
    });
  };
  const confirmAndActivate = () => {
    if (!scan || busy || account?.membership_state) return;
    void execute(async () => {
      const result = await accountRequest<{ status: string; verification_source: string; schedule: Match }>(
        `registration-documents/${scan.id}/confirm`, 'POST', {}, 25_000,
      );
      setMatch(result.schedule);
      setNotice('Your account is active. We checked your confirmed courses against published classes.');
      session.refresh();
      requestAnimationFrame(() => resultHeading.current?.focus());
    });
  };
  const reviewValid = /^\d{4}-\d{4}$/.test(review.academic_year)
    && ['first', 'second'].includes(review.semester)
    && /^[0-9]{2}-[0-9]{5}$/.test(review.student_identifier)
    && !!review.program.trim()
    && /^[1-4]$/.test(review.year_level)
    && review.courses.length > 0
    && review.courses.every((course) => !!course.code.trim());
  if (session.state.status === 'authorized' && session.state.membership.role !== 'student')
    return (
      <section className="workspace-card">
        <h1>Student access required</h1>
        <Link to="/auth/login">Check your account</Link>
      </section>
    );
  return (
    <section className="registration-scanner workspace-card" aria-busy={busy}>
      <Link to={session.state.status === 'authorized' ? '/student/dashboard' : '/auth/login'}>
        Back to your account
      </Link>
      <h1>Scan your registration form</h1>
      <p>
        Review your courses, then find the published classes linked to your verified enrollment.
      </p>
      <p className="muted">
        Private processing · Your original file is deleted after reading. Temporary extracted fields
        expire within 15 minutes.
      </p>
      {error && (
        <div role="alert" className="registration-error">
          {error}
        </div>
      )}
      {notice && <p role="status">{notice}</p>}
      {!account ? (
        <>
          <p role="status">Checking account status…</p>
          <Button onClick={() => setLoad((value) => value + 1)}>Retry account status</Button>
        </>
      ) : !account.email_verified ? (
        <>
          <p>Verify your email before uploading a registration form.</p>
          <Link className="button" to="/auth/login">
            Verify your account
          </Link>
        </>
      ) : ['revoked', 'inactive'].includes(account.membership_state ?? '') ? (
        <p>Your university access is inactive. Contact your university for help.</p>
      ) : (
        <>
          {!scan ? (
            <div className="registration-upload">
              <label htmlFor="registration-file">Choose a PDF or clear photo</label>
              <input
                ref={fileInput}
                id="registration-file"
                type="file"
                accept="application/pdf,image/jpeg,image/png"
                disabled={busy}
                onChange={(event) => {
                  const file = event.target.files?.[0];
                  if (file) void begin(file);
                }}
              />
              <p>
                PDF, JPEG or PNG. File size and page limits apply. Use a clear, complete view of the
                academic section.
              </p>
              <Button disabled={busy} variant="secondary" onClick={() => void begin()}>
                Enter courses manually
              </Button>
            </div>
          ) : (
            <>
              <h2 ref={heading} tabIndex={-1}>
                Review your classes
              </h2>
              <p>Check your scanned details and tap Confirm to load your schedule.</p>
              {!review.student_identifier && (
                <p className="registration-review-note" role="note">
                  Re-enter your student number to continue.
                </p>
              )}
              {scan.warnings.map((warning) => (
                <p key={warning} className="muted">
                  {warning}
                </p>
              ))}
              <form onSubmit={submit}>
                <fieldset disabled={busy} className="registration-fields">
                  <legend>Academic details</legend>
                  <div>
                    <label htmlFor="scan-year">Academic year</label>
                    <input
                      id="scan-year"
                      required
                      pattern="[0-9]{4}-[0-9]{4}"
                      placeholder="2026-2027"
                      value={review.academic_year}
                      onChange={(e) => edit({ academic_year: e.target.value })}
                    />
                  </div>
                  <div>
                    <label htmlFor="scan-semester">Semester</label>
                    <select
                      id="scan-semester"
                      required
                      value={review.semester}
                      onChange={(e) => edit({ semester: e.target.value })}
                    >
                      <option value="">Choose semester</option>
                      <option value="first">First semester</option>
                      <option value="second">Second semester</option>
                    </select>
                  </div>
                  <div>
                    <label htmlFor="scan-student">Student number</label>
                    <input
                      id="scan-student"
                      required
                      minLength={8}
                      maxLength={8}
                      pattern="[0-9]{2}-[0-9]{5}"
                      placeholder="12-12345"
                      autoComplete="off"
                      value={review.student_identifier}
                      onChange={(e) => edit({ student_identifier: formatStudentNumber(e.target.value) })}
                    />
                  </div>
                  <div>
                    <label htmlFor="scan-program">Program</label>
                    <select
                      id="scan-program"
                      value={review.program}
                      onChange={(e) => edit({ program: e.target.value })}
                    >
                      <option value="">Choose program</option>
                      {CDM_PROGRAMS.map((program) => <option key={program} value={program}>{program}</option>)}
                    </select>
                  </div>
                  <div>
                    <label htmlFor="scan-level">Year level</label>
                    <select
                      id="scan-level"
                      value={review.year_level}
                      onChange={(e) => edit({ year_level: e.target.value })}
                    >
                      <option value="">Choose year level</option>
                      {[1, 2, 3, 4].map((level) => (
                        <option key={level} value={level}>Year {level}</option>
                      ))}
                    </select>
                  </div>
                </fieldset>
                <h3>Courses on your form</h3>
                <p>Enter each course exactly as it appears on your form.</p>
                <div className="registration-courses">
                  {review.courses.map((course, index) => (
                    <fieldset className="registration-course" disabled={busy} key={index}>
                      <legend className="visually-hidden">Course {index + 1}</legend>
                      <div>
                      <label htmlFor={`course-code-${index}`}>Course code</label>
                      <input
                        id={`course-code-${index}`}
                        required
                        maxLength={40}
                        value={course.code}
                        onChange={(e) => editCourse(index, { code: e.target.value })}
                      />
                      </div>
                      <div>
                      <label htmlFor={`course-section-${index}`}>Enrollment section on form</label>
                      <input
                        id={`course-section-${index}`}
                        maxLength={80}
                        value={course.section}
                        onChange={(e) => editCourse(index, { section: e.target.value })}
                      />
                      </div>
                      <div>
                      <label className="visually-hidden" htmlFor={`course-description-${index}`}>Course description</label>
                      <input
                        id={`course-description-${index}`}
                        aria-label={`Course ${index + 1} description`}
                        maxLength={240}
                        placeholder="Course description"
                        value={course.description}
                        onChange={(e) => editCourse(index, { description: e.target.value })}
                      />
                      </div>
                      <Button
                        variant="ghost"
                        type="button"
                        disabled={review.courses.length <= 1}
                        onClick={() =>
                          edit({ courses: review.courses.filter((_, i) => i !== index) })
                        }
                      >
                        Remove course {index + 1}
                      </Button>
                    </fieldset>
                  ))}
                </div>
                <details className="registration-raw-details">
                  <summary>View raw scan details</summary>
                  <ul>
                    {Object.entries(scan.fields).map(([key, field]) => field && (
                      <li key={key}>{key.replaceAll('_', ' ')} · Page {field.evidence.page}: {String(field.value)}</li>
                    ))}
                    {scan.courses.map((course, index) => (
                      <li key={index}>Course {index + 1} · Page {course.code.evidence.page}: {String(course.code.value)} · Section: {String(course.section.value)}</li>
                    ))}
                  </ul>
                </details>
                <div className="registration-actions">
                  <Button
                    type="button"
                    variant="secondary"
                    disabled={busy || review.courses.length >= 60}
                    onClick={() =>
                      edit({
                        courses: [...review.courses, { code: '', description: '', section: '' }],
                      })
                    }
                  >
                    Add a course
                  </Button>
                  <Button type="submit" disabled={busy || !reviewValid}>
                    Find my classes
                  </Button>
                </div>
              </form>
              {match && (
                <section aria-labelledby="scan-match-title">
                  <h2 id="scan-match-title" ref={resultHeading} tabIndex={-1}>
                    {match.status === 'matched'
                      ? 'Your verified classes'
                      : 'Verification or matching needed'}
                  </h2>
                  <p role="status">{match.message}</p>
                  <ul>
                    {match.courses.map((course, index) => (
                      <li key={index}>
                        <strong>{course.code}</strong> ·{' '}
                        {course.status === 'matched'
                          ? 'Matched to verified enrollment'
                          : course.status === 'ambiguous'
                            ? 'More than one possible offering'
                            : 'Needs university review'}
                        {course.offering && (
                          <p>Published section: {course.offering.section.name}</p>
                        )}
                      </li>
                    ))}
                  </ul>
                  {match.status === 'matched' &&
                    match.periods?.map((period) => (
                      <Link
                        className="button"
                        key={period.id}
                        to={`/student/schedule?period=${encodeURIComponent(period.id)}${period.start ? `&date=${period.start}` : ''}`}
                      >
                        View verified schedule
                      </Link>
                    ))}
                  {match.status === 'pending-verification' && account.verification_mode === 'strict_roster' &&
                    !account.claim_state &&
                    !account.membership_state && (
                      <>
                        <p>
                          Your student number is not on the current Registrar roster. Request an administrator review.
                        </p>
                        <Button
                          disabled={busy}
                          onClick={() =>
                            void execute(async () => {
                              await accountRequest('student-claims', 'POST', {
                                student_id: review.student_identifier,
                              });
                              setAccount(await accountRequest<OnboardingStatus>('onboarding'));
                              setNotice(
                                'Your student record request is awaiting university verification.',
                              );
                            })
                          }
                        >
                          Request student verification
                        </Button>
                      </>
                    )}
                  {account.claim_state === 'pending' && (
                    <p>Your student record request is awaiting university verification.</p>
                  )}
                </section>
              )}
              {match?.status === 'pending-verification' && !account.membership_state &&
                account.verification_mode !== 'strict_roster' && (
                  <section className="registration-activation" aria-label="Activate student access">
                    <h3>Ready to activate your access?</h3>
                    <p>Confirm the reviewed Registration Form to link this account and check for published classes.</p>
                    <Button disabled={busy} onClick={confirmAndActivate}>
                      Confirm Registration Form
                    </Button>
                  </section>
                )}
              <Button disabled={busy} variant="ghost" onClick={erase}>
                Delete temporary scan
              </Button>
            </>
          )}
        </>
      )}
      {busy && (
        <p role="status">{scan ? 'Checking your request…' : 'Reading your form privately…'}</p>
      )}
    </section>
  );
}
