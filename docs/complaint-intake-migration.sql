BEGIN;
ALTER TABLE complaint ADD COLUMN submitter_user_id INTEGER;
ALTER TABLE complaint ADD CONSTRAINT fk_complaint_submitter_user_id_user FOREIGN KEY (submitter_user_id) REFERENCES "user"(id);
CREATE INDEX ix_complaint_submitter_user_id ON complaint(submitter_user_id);
ALTER TABLE attachment ADD COLUMN uploaded_by INTEGER;
ALTER TABLE attachment ADD COLUMN upload_key VARCHAR(100);
ALTER TABLE attachment ADD CONSTRAINT fk_attachment_uploaded_by_user FOREIGN KEY (uploaded_by) REFERENCES "user"(id);
ALTER TABLE attachment ADD CONSTRAINT uq_attachment_complaint_upload_key UNIQUE (complaint_id, upload_key);
CREATE TABLE complaint_report (
  id SERIAL PRIMARY KEY,
  complaint_id INTEGER NOT NULL REFERENCES complaint(id),
  closure_event_id INTEGER NOT NULL UNIQUE REFERENCES action_event(id),
  created_at TIMESTAMP WITH TIME ZONE NOT NULL,
  pdf BYTEA NOT NULL,
  checksum VARCHAR(64) NOT NULL
);
CREATE INDEX ix_complaint_report_complaint_id ON complaint_report(complaint_id);
UPDATE alembic_version SET version_num='c7b409d2e106' WHERE version_num='af4e310ce902';
COMMIT;
