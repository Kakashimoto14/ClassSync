import { Link } from 'react-router-dom';
import { useState, type FormEvent } from 'react';
import { Button } from '../components/ui/Button';
import { accountRequest as requestAccount } from './account-actions';
import { isValidAccountEmail, normalizeAccountEmail } from './student-number';

interface Claim {
  uid: string;
  student_id: string;
  state: string;
}
interface SelfVerifiedStudent {
  uid: string;
  student_id: string;
  registered_email: string;
  verification_source: 'cor_self_verified';
  membership_revision: number;
}
interface Invitation {
  id: string;
  token: string;
  expires_in_hours: number;
}

export function AccountAdministrationPanel({ uid }: { uid: string }) {
  const accountRequest = <T,>(path: string, method = 'GET', body?: unknown) =>
    requestAccount<T>(path, method, body, undefined, uid);
  const [claims, setClaims] = useState<Claim[]>([]);
  const [faculty, setFaculty] = useState<{ id: string }[]>([]);
  const [selfVerified, setSelfVerified] = useState<SelfVerifiedStudent[]>([]);
  const [selected, setSelected] = useState('');
  const [email, setEmail] = useState('');
  const [reference, setReference] = useState('');
  const [invitation, setInvitation] = useState<Invitation | null>(null);
  const [confirmRevokeUid, setConfirmRevokeUid] = useState('');
  const [revokeUid, setRevokeUid] = useState('');
  const [revision, setRevision] = useState('');
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);
  const run = async (work: () => Promise<void>) => {
    setBusy(true);
    setMessage('');
    try {
      await work();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Account service unavailable.');
    } finally {
      setBusy(false);
    }
  };
  const load = async () => {
    const [nextClaims, nextFaculty, nextSelfVerified] = await Promise.all([
      accountRequest<Claim[]>('student-claims'),
      accountRequest<{ id: string }[]>('faculty-records'),
      accountRequest<SelfVerifiedStudent[]>('self-verified-students'),
    ]);
    setClaims(nextClaims);
    setFaculty(nextFaculty);
    setSelfVerified(nextSelfVerified);
    setMessage(
      nextClaims.length
        ? 'Review each request against your authorized institutional identity source.'
        : nextSelfVerified.length
          ? `${nextSelfVerified.length} student account${nextSelfVerified.length === 1 ? '' : 's'} activated from a confirmed form; review or revoke below.`
          : 'No pending student requests.',
    );
  };
  const invite = (event: FormEvent) => {
    event.preventDefault();
    void run(async () => {
      setInvitation(null);
      const result = await accountRequest<Invitation>('faculty-invitations', 'POST', {
        faculty_id: selected,
        email: normalizeAccountEmail(email),
        expires_in_hours: 48,
      });
      setInvitation(result);
      setMessage('Invitation created. Share this code privately with the approved faculty member.');
    });
  };
  return (
    <section aria-label="University account management" aria-busy={busy}>
      <h3>University accounts</h3>
      <p>Review pending records and monitor students activated from confirmed Registration Forms.</p>
      <Button disabled={busy} onClick={() => void run(load)}>
        Load account requests
      </Button>
      <p role="status">{message}</p>
      {claims.length > 0 && (
        <>
          <label htmlFor="identity-review-reference">Identity verification reference</label>
          <input
            id="identity-review-reference"
            required
            maxLength={500}
            value={reference}
            onChange={(e) => setReference(e.target.value)}
          />
          <p>
            Record a reference to your approved verification process; do not paste identity
            documents here.
          </p>
          <ul>
            {claims.map((claim) => (
              <li key={claim.uid}>
                Student number: {claim.student_id}
                <Button
                  disabled={busy || !reference.trim()}
                  onClick={() =>
                    void run(async () => {
                      await accountRequest(
                        `student-claims/${encodeURIComponent(claim.uid)}`,
                        'PATCH',
                        { approve: true, verification_reference: reference },
                      );
                      await load();
                    })
                  }
                >
                  Approve student {claim.student_id}
                </Button>
                <Button
                  disabled={busy || !reference.trim()}
                  variant="secondary"
                  onClick={() =>
                    void run(async () => {
                      await accountRequest(
                        `student-claims/${encodeURIComponent(claim.uid)}`,
                        'PATCH',
                        { approve: false, verification_reference: reference },
                      );
                      await load();
                    })
                  }
                >
                  Reject student {claim.student_id}
                </Button>
              </li>
            ))}
          </ul>
        </>
      )}
      {selfVerified.length > 0 && (
        <section aria-labelledby="self-verified-students-heading">
          <h4 id="self-verified-students-heading">Students activated from a Registration Form</h4>
          <p>These accounts are marked for administrator review. Revoke access if the record is invalid.</p>
          <ul>
            {selfVerified.map((student) => (
              <li key={student.uid}>
                <strong>{student.student_id}</strong> · {student.registered_email}
                <span> · Form verified · Revision {student.membership_revision}</span>
                {confirmRevokeUid === student.uid ? (
                  <div role="group" aria-label={`Confirm access revocation for ${student.student_id}`}>
                    <p>Revoke access for student {student.student_id}?</p>
                    <Button
                      disabled={busy}
                      onClick={() => void run(async () => {
                        await accountRequest(
                          `memberships/${encodeURIComponent(student.uid)}/revoke`,
                          'PATCH',
                          { expected_revision: student.membership_revision },
                        );
                        setConfirmRevokeUid('');
                        await load();
                        setMessage(`Access revoked for student ${student.student_id}.`);
                      })}
                    >
                      Confirm revoke
                    </Button>
                    <Button
                      disabled={busy}
                      variant="ghost"
                      onClick={() => setConfirmRevokeUid('')}
                    >
                      Cancel revoke
                    </Button>
                  </div>
                ) : (
                  <Button
                    disabled={busy}
                    variant="secondary"
                    onClick={() => setConfirmRevokeUid(student.uid)}
                  >
                    Revoke access
                  </Button>
                )}
              </li>
            ))}
          </ul>
        </section>
      )}
      <form onSubmit={invite}>
        <h4>Invite a faculty member</h4>
        <label htmlFor="faculty-record">Approved faculty record</label>
        <select
          id="faculty-record"
          required
          value={selected}
          onChange={(e) => setSelected(e.target.value)}
        >
          <option value="">Choose a faculty record</option>
          {faculty.map((record) => (
            <option key={record.id} value={record.id}>
              {record.id}
            </option>
          ))}
        </select>
        <label htmlFor="faculty-email">Approved email</label>
        <input
          id="faculty-email"
          type="email"
          required
          maxLength={320}
          autoCapitalize="none"
          autoComplete="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
        <Button type="submit" disabled={busy || !selected || !isValidAccountEmail(email)}>
          Create private invitation
        </Button>
      </form>
      {invitation && (
        <div>
          <p>
            This code expires in {invitation.expires_in_hours} hours and can be accepted once by the
            approved email account.
          </p>
          <p>
            <Link to="/auth/teacher-invite">Open the invitation sign-in page</Link>
          </p>
          <label htmlFor="private-invitation">Private invitation code</label>
          <input id="private-invitation" readOnly value={invitation.token} />
          <Button
            disabled={busy}
            variant="secondary"
            onClick={() =>
              void run(async () => {
                await accountRequest(`faculty-invitations/${invitation.id}`, 'DELETE');
                setInvitation(null);
                setMessage('Invitation revoked.');
              })
            }
          >
            Revoke invitation
          </Button>
        </div>
      )}
      <details>
        <summary>Revoke university membership</summary>
        <form
          onSubmit={(event) => {
            event.preventDefault();
            void run(async () => {
              await accountRequest(`memberships/${encodeURIComponent(revokeUid)}/revoke`, 'PATCH', {
                expected_revision: Number(revision),
              });
              setMessage('University membership revoked.');
            });
          }}
        >
          <label htmlFor="revoke-account">Verified account reference</label>
          <input
            id="revoke-account"
            required
            maxLength={128}
            value={revokeUid}
            onChange={(e) => setRevokeUid(e.target.value)}
          />
          <label htmlFor="revoke-revision">Current membership revision</label>
          <input
            id="revoke-revision"
            type="number"
            min={1}
            required
            value={revision}
            onChange={(e) => setRevision(e.target.value)}
          />
          <Button type="submit" disabled={busy}>
            Revoke university access
          </Button>
        </form>
      </details>
    </section>
  );
}
