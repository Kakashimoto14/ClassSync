CREATE TABLE solver_runs_v2 (
 id TEXT PRIMARY KEY,
 scope TEXT NOT NULL CHECK(scope IN ('sandbox','academic-sandbox','administrator')),
 owner TEXT NOT NULL, created_at TEXT NOT NULL,
 schema_version INTEGER NOT NULL CHECK(schema_version=1),
 payload TEXT NOT NULL CHECK(json_valid(payload)), checksum TEXT NOT NULL
);
CREATE TABLE scheduling_drafts_v2 (
 id TEXT PRIMARY KEY, run_id TEXT NOT NULL UNIQUE REFERENCES solver_runs_v2(id),
 scope TEXT NOT NULL CHECK(scope IN ('sandbox','academic-sandbox','administrator')),
 owner TEXT NOT NULL, title TEXT NOT NULL CHECK(length(trim(title)) BETWEEN 1 AND 160),
 created_at TEXT NOT NULL, schema_version INTEGER NOT NULL CHECK(schema_version=1),
 status TEXT NOT NULL DEFAULT 'draft' CHECK(status='draft'),
 idempotency_key TEXT NOT NULL, payload TEXT NOT NULL CHECK(json_valid(payload)),
 checksum TEXT NOT NULL, UNIQUE(scope,owner,idempotency_key)
);
INSERT INTO solver_runs_v2 SELECT * FROM solver_runs;
INSERT INTO scheduling_drafts_v2 SELECT * FROM scheduling_drafts;
DROP TABLE scheduling_drafts;
DROP TABLE solver_runs;
ALTER TABLE solver_runs_v2 RENAME TO solver_runs;
ALTER TABLE scheduling_drafts_v2 RENAME TO scheduling_drafts;
CREATE INDEX drafts_by_owner ON scheduling_drafts(scope,owner,created_at DESC,id DESC);
CREATE TRIGGER immutable_draft BEFORE UPDATE ON scheduling_drafts
BEGIN SELECT RAISE(ABORT,'Saved drafts are immutable'); END;
