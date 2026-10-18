CREATE TABLE academic_periods (
 scope TEXT NOT NULL CHECK(scope IN ('sandbox','administrator')), owner TEXT NOT NULL,
 id TEXT NOT NULL, title TEXT NOT NULL CHECK(length(trim(title))>0),
 revision INTEGER NOT NULL CHECK(revision>0), created_at TEXT NOT NULL,
 PRIMARY KEY(scope,owner,id)
);
CREATE TABLE academic_records (
 scope TEXT NOT NULL, owner TEXT NOT NULL, period_id TEXT NOT NULL,
 kind TEXT NOT NULL CHECK(kind IN ('programs','subjects','sections','faculty','resources','offerings','constraints')),
 id TEXT NOT NULL, revision INTEGER NOT NULL CHECK(revision>0),
 unique_label TEXT NOT NULL, updated_at TEXT NOT NULL, updated_by TEXT NOT NULL,
 payload TEXT NOT NULL CHECK(json_valid(payload)), checksum TEXT NOT NULL,
 PRIMARY KEY(scope,owner,period_id,kind,id),
 UNIQUE(scope,owner,period_id,kind,unique_label),
 FOREIGN KEY(scope,owner,period_id) REFERENCES academic_periods(scope,owner,id) ON DELETE RESTRICT
);
CREATE TABLE academic_references (
 scope TEXT NOT NULL, owner TEXT NOT NULL, period_id TEXT NOT NULL,
 source_kind TEXT NOT NULL, source_id TEXT NOT NULL, target_kind TEXT NOT NULL, target_id TEXT NOT NULL,
 PRIMARY KEY(scope,owner,period_id,source_kind,source_id,target_kind,target_id),
 FOREIGN KEY(scope,owner,period_id,source_kind,source_id) REFERENCES academic_records(scope,owner,period_id,kind,id) ON DELETE CASCADE,
 FOREIGN KEY(scope,owner,period_id,target_kind,target_id) REFERENCES academic_records(scope,owner,period_id,kind,id) ON DELETE RESTRICT
);
