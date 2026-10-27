-- Production repair matching the committed Alembic migrations:
-- 8d42c1e7a905, 61b37e20a4f8, d72fa0981c43 and af4e310ce902.
-- Generated passwords are discarded. Public demos use /auth/demo-login.
BEGIN;
ALTER TABLE "user" ADD COLUMN requested_role VARCHAR(30);
ALTER TABLE "user" ADD COLUMN organization VARCHAR(200);
CREATE UNIQUE INDEX uq_single_system_administrator ON "user" (role) WHERE role = 'admin';
CREATE TABLE password_reset (
  id VARCHAR(64) PRIMARY KEY,
  user_id INTEGER NOT NULL,
  created_at TIMESTAMP WITH TIME ZONE NOT NULL,
  expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
  used_at TIMESTAMP WITH TIME ZONE,
  CONSTRAINT fk_password_reset_user_id_user FOREIGN KEY(user_id) REFERENCES "user"(id)
);
CREATE INDEX ix_password_reset_user_id ON password_reset(user_id);
ALTER TABLE "user" ADD COLUMN is_demo BOOLEAN NOT NULL DEFAULT FALSE;
INSERT INTO bureau (code,name) VALUES ('PUBLIC-DEMO','Public demonstration bureau') ON CONFLICT (code) DO NOTHING;
INSERT INTO institution (name,external_id,verified,region,address)
VALUES ('OneCase Demonstration Institute','ONECASE-PUBLIC-DEMO',FALSE,'Demonstration','Synthetic institution for public demonstrations')
ON CONFLICT (external_id) DO NOTHING;
INSERT INTO "user" (name,email,password_hash,role,requested_role,organization,bureau_id,active,is_demo,mfa_enabled,recovery_codes) VALUES ('Demo Student','demo.student@onecase.demo','$argon2id$v=19$m=65536,t=3,p=4$SMjUtxlrWn7w4okMb+ChKA$nrF7bYI3R/1Yjei0fBTMNU8zg4O9Uxnj1Kwyb3RuYM8','student','student','OneCase public demonstration',NULL,TRUE,TRUE,FALSE,'[]'::json) ON CONFLICT (email) DO NOTHING;
INSERT INTO "user" (name,email,password_hash,role,requested_role,organization,bureau_id,active,is_demo,mfa_enabled,recovery_codes) VALUES ('Demo Parent','demo.parent@onecase.demo','$argon2id$v=19$m=65536,t=3,p=4$czFz9kdf3/a2sehjWV95MQ$ixBMdeoUCFDlX4NxgL59YGr6AN18kMVHgJCZ496yN1c','parent','parent','OneCase public demonstration',NULL,TRUE,TRUE,FALSE,'[]'::json) ON CONFLICT (email) DO NOTHING;
INSERT INTO "user" (name,email,password_hash,role,requested_role,organization,bureau_id,active,is_demo,mfa_enabled,recovery_codes) VALUES ('Demo Faculty','demo.faculty@onecase.demo','$argon2id$v=19$m=65536,t=3,p=4$A88SBrqIYSXh1twmrlum1w$xZHSRzIIOcXGYgA/DwJBXZARCmfAxD9qsD629YOs3CE','faculty','faculty','OneCase public demonstration',NULL,TRUE,TRUE,FALSE,'[]'::json) ON CONFLICT (email) DO NOTHING;
INSERT INTO "user" (name,email,password_hash,role,requested_role,organization,bureau_id,active,is_demo,mfa_enabled,recovery_codes) VALUES ('Demo Staff','demo.staff@onecase.demo','$argon2id$v=19$m=65536,t=3,p=4$oJF3hgHJN7rtDrZWjQvpdQ$LN7OIZuv8DRrVClI7mNHea4u2rPns2Zo3c+2GI27ML4','staff','staff','OneCase public demonstration',NULL,TRUE,TRUE,FALSE,'[]'::json) ON CONFLICT (email) DO NOTHING;
INSERT INTO "user" (name,email,password_hash,role,requested_role,organization,bureau_id,active,is_demo,mfa_enabled,recovery_codes) VALUES ('Demo Other','demo.other@onecase.demo','$argon2id$v=19$m=65536,t=3,p=4$6juN5mRIuOOpYHRpOM5DnA$4/tpdcCcoVCvWRggxyGEO4I+9sXcyFJ0YSBrY6BvZmc','other','other','OneCase public demonstration',NULL,TRUE,TRUE,FALSE,'[]'::json) ON CONFLICT (email) DO NOTHING;
INSERT INTO "user" (name,email,password_hash,role,requested_role,organization,bureau_id,active,is_demo,mfa_enabled,recovery_codes) VALUES ('Demo Officer','demo.officer@onecase.demo','$argon2id$v=19$m=65536,t=3,p=4$EsffiBURrdmGYc6+pUBIDA$39HYzLtl4QlDia+TXmXCj6GDOQBrw26qBkD6PY/8LRw','officer','officer','OneCase public demonstration',(SELECT id FROM bureau WHERE code='PUBLIC-DEMO'),TRUE,TRUE,FALSE,'[]'::json) ON CONFLICT (email) DO NOTHING;
INSERT INTO "user" (name,email,password_hash,role,requested_role,organization,bureau_id,active,is_demo,mfa_enabled,recovery_codes) VALUES ('Demo Lead','demo.lead@onecase.demo','$argon2id$v=19$m=65536,t=3,p=4$7CYwuoxXyzeP9S+B8+30Fg$rhwJlZ1fJabA/u2C/RYyBa90BXLBrgx6pa8cGF4OSi4','lead','lead','OneCase public demonstration',(SELECT id FROM bureau WHERE code='PUBLIC-DEMO'),TRUE,TRUE,FALSE,'[]'::json) ON CONFLICT (email) DO NOTHING;
INSERT INTO "user" (name,email,password_hash,role,requested_role,organization,bureau_id,active,is_demo,mfa_enabled,recovery_codes) VALUES ('Demo Reviewer','demo.reviewer@onecase.demo','$argon2id$v=19$m=65536,t=3,p=4$hPi0IimMHqVgLVOvybcxCw$gXmlJpzbO+HnaNg8fM4g8w2JyPwgngZ22IpT6OhR7/4','reviewer','reviewer','OneCase public demonstration',NULL,TRUE,TRUE,FALSE,'[]'::json) ON CONFLICT (email) DO NOTHING;
INSERT INTO "user" (name,email,password_hash,role,requested_role,organization,bureau_id,active,is_demo,mfa_enabled,recovery_codes) VALUES ('Demo Committee','demo.committee@onecase.demo','$argon2id$v=19$m=65536,t=3,p=4$0b5k62b7gZRR/pa3W9sH7A$yCGqXZEKPIvTDFTjUipfKwARli+Vncb73/j1kjG0xvs','committee','committee','OneCase public demonstration',NULL,TRUE,TRUE,FALSE,'[]'::json) ON CONFLICT (email) DO NOTHING;
INSERT INTO "user" (name,email,password_hash,role,requested_role,organization,bureau_id,active,is_demo,mfa_enabled,recovery_codes) VALUES ('Demo Verifier','demo.verifier@onecase.demo','$argon2id$v=19$m=65536,t=3,p=4$3mV1u5tnK8GefqLd2Ho6kQ$n73G2gcU7l9QphEymP59d5+Zt0wxIsSbQcmmilhG67w','verifier','verifier','OneCase public demonstration',NULL,TRUE,TRUE,FALSE,'[]'::json) ON CONFLICT (email) DO NOTHING;
INSERT INTO "user" (name,email,password_hash,role,requested_role,organization,bureau_id,active,is_demo,mfa_enabled,recovery_codes) VALUES ('Demo Executive','demo.executive@onecase.demo','$argon2id$v=19$m=65536,t=3,p=4$nJtriYJrMG0vxPWCJaAe8w$nTQhWPmN7CUaFzkTOpSTpVw28zlXjWyf4xVOQbncoHk','executive','executive','OneCase public demonstration',NULL,TRUE,TRUE,FALSE,'[]'::json) ON CONFLICT (email) DO NOTHING;
INSERT INTO "user" (name,email,password_hash,role,requested_role,organization,bureau_id,active,is_demo,mfa_enabled,recovery_codes) VALUES ('Demo Auditor','demo.auditor@onecase.demo','$argon2id$v=19$m=65536,t=3,p=4$GbYp5oZkwOMrnCVdaBpXHA$0Kx76UNN1X6xAfjEBIhwLKanBHlBo0iinxHHJaVvP/M','auditor','auditor','OneCase public demonstration',NULL,TRUE,TRUE,FALSE,'[]'::json) ON CONFLICT (email) DO NOTHING;
UPDATE alembic_version SET version_num='af4e310ce902' WHERE version_num='40177bd277c9';
COMMIT;
