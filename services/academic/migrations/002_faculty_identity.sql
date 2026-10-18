CREATE UNIQUE INDEX faculty_institutional_identity
ON academic_records(scope,owner,period_id,lower(trim(json_extract(payload,'$.institutional_id'))))
WHERE kind='faculty'
AND json_extract(payload,'$.institutional_id') IS NOT NULL
AND trim(json_extract(payload,'$.institutional_id')) <> '';
