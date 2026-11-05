# M2 private registration scanner acceptance

- Verified signed-in users upload bounded PDF/JPEG/PNG through the Gateway. Reject
  signature/content mismatch, malformed/active/encrypted PDFs, oversized inputs/pages,
  oversized images and unauthorized requests. Bound processing memory/time/concurrency.
- Digital text first; local bounded OCR for scans/photos. No cloud document upload.
  Missing OCR/provider errors remain visible; never simulate successful extraction.
- Extract only academic year/semester, private student identifier, program/year and
  course code/description/raw enrollment section. Return reviewable evidence and
  honest confidence availability. Discard financial/signature/unrelated personal fields.
- Review/correct extracted fields. Numeric enrollment sections remain numeric raw
  values. Never derive named sections, times, faculty or rooms from the document.
- Match only a current authorized Student enrollment against an exact published term
  and offering data. No document or reviewed identifier independently links membership.
  Unlinked, wrong term, ambiguous/unmatched and unavailable results stay explicit.
- Private temporary processing, immediate original-file deletion, bounded extracted
  result retention, per-user ownership, no document URLs/body logs, request throttling.
- Repeatable fixtures contain invented/redacted data only. Qualify PDF/photo extraction,
  corrections, negative files/authorization/ownership and connected matching UI.
  Inspect real form locally in memory; report only structural/assertion outcomes.
