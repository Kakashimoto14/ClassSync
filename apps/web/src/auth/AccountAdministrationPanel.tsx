import { useState, type FormEvent } from 'react';
import { Button } from '../components/ui/Button';
import { accountRequest } from './account-actions';

interface Claim {
  uid: string;
  student_id: string;
  state: string;
}
interface Invitation {
  id: string;
  token: string;
  expires_in_hours: number;
}

export function AccountAdministrationPanel() {
  const [claims, setClaims] = useState<Claim[]>([]);
  const [faculty, setFaculty] = useState<{ id: string }[]>([]);
  const [selected, setSelected] = useState('');
  const [email, setEmail] = useState('');
  const [reference, setReference] = useState('');
  const [invitation, setInvitation] = useState<Invitation | null>(null);
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
    const [nextClaims, nextFaculty] = await Promise.all([
      accountRequest<Claim[]>('student-claims'),
      accountRequest<{ id: string }[]>('faculty-records'),
    ]);
    setClaims(nextClaims);
    setFaculty(nextFaculty);
    setMessage(
      nextClaims.length
        ? 'Review each request against your authorized institutional identity source.'
        : 'No pending student requests.',
    );
  };
  const invite = (event: FormEvent) => {
    event.preventDefault();
    void run(async () => {
      setInvitation(null);
      const result = await accountRequest<Invitation>('faculty-invitations', 'POST', {
        faculty_id: selected,
        email,
        expires_in_hours: 48,
      });
      setInvitation(result);
      setMessage('Invitation created. Share this code privately with the approved faculty member.');
    });
  };
  return (
    <section aria-label="University account management" aria-busy={busy}>
      <h3>University accounts</h3>
      <p>
        Use an authorized identity source to verify student requests. Submitted numbers and
        registration images alone are insufficient.
      </p>
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
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
        <Button type="submit" disabled={busy}>
          Create private invitation
        </Button>
      </form>
      {invitation && (
        <div>
          <p>
            This code expires in {invitation.expires_in_hours} hours and can be accepted once by the
            approved email account.
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
