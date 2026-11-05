import { useEffect, useRef, useState, type FormEvent } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { accountRequest, observeAccount, type OnboardingStatus } from '../auth/account-actions';
import { useUniversitySession } from '../auth/university-session-context';
import { appMode } from '../config/runtime-config';
import { Button } from '../components/ui/Button';
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
    student_identifier: value('student_identifier'),
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
function Source({ field, label }: { field?: Evidence; label: string }) {
  return field ? (
    <details className="registration-source">
      <summary>Source for {label}</summary>
      <p>
        Page {field.evidence.page}: {String(field.value)}
      </p>
      <p>Check this field against your form.</p>
    </details>
  ) : null;
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
              <p>
                {scan.method === 'manual'
                  ? 'Enter the academic details from your form.'
                  : 'Check every extracted field against your form. Extraction confidence is unavailable; your review is required.'}
              </p>
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
                    <Source field={scan.fields.academic_year} label="academic year" />
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
                    <Source field={scan.fields.semester} label="semester" />
                  </div>
                  <div>
                    <label htmlFor="scan-student">Student number</label>
                    <input
                      id="scan-student"
                      required
                      maxLength={128}
                      autoComplete="off"
                      value={review.student_identifier}
                      onChange={(e) => edit({ student_identifier: e.target.value })}
                    />
                    <Source field={scan.fields.student_identifier} label="student number" />
                  </div>
                  <div>
                    <label htmlFor="scan-program">Program</label>
                    <input
                      id="scan-program"
                      maxLength={160}
                      value={review.program}
                      onChange={(e) => edit({ program: e.target.value })}
                    />
                    <Source field={scan.fields.program} label="program" />
                  </div>
                  <div>
                    <label htmlFor="scan-level">Year level</label>
                    <input
                      id="scan-level"
                      type="number"
                      min={1}
                      max={20}
                      value={review.year_level}
                      onChange={(e) => edit({ year_level: e.target.value })}
                    />
                    <Source field={scan.fields.year_level} label="year level" />
                  </div>
                </fieldset>
                <h3>Courses on your form</h3>
                <p>
                  Copy enrollment sections exactly as shown. A number alone does not identify an
                  institutional section.
                </p>
                <div className="registration-courses">
                  {review.courses.map((course, index) => (
                    <fieldset className="registration-course" disabled={busy} key={index}>
                      <legend>Course {index + 1}</legend>
                      <label htmlFor={`course-code-${index}`}>Course code</label>
                      <input
                        id={`course-code-${index}`}
                        required
                        maxLength={40}
                        value={course.code}
                        onChange={(e) => editCourse(index, { code: e.target.value })}
                      />
                      <Source
                        field={scan.courses[course.sourceIndex ?? -1]?.code}
                        label={`course ${index + 1} code`}
                      />
                      <label htmlFor={`course-section-${index}`}>Enrollment section on form</label>
                      <input
                        id={`course-section-${index}`}
                        maxLength={80}
                        value={course.section}
                        onChange={(e) => editCourse(index, { section: e.target.value })}
                      />
                      <Source
                        field={scan.courses[course.sourceIndex ?? -1]?.section}
                        label={`course ${index + 1} section`}
                      />
                      <details>
                        <summary>Course description</summary>
                        <label htmlFor={`course-description-${index}`}>Description</label>
                        <input
                          id={`course-description-${index}`}
                          maxLength={240}
                          value={course.description}
                          onChange={(e) => editCourse(index, { description: e.target.value })}
                        />
                      </details>
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
                  <Button type="submit" disabled={busy}>
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
                  {match.status === 'pending-verification' &&
                    !account.claim_state &&
                    !account.membership_state && (
                      <>
                        <p>
                          Your university must verify your institutional identity. A student number
                          or form alone cannot activate access.
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
