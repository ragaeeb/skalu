ALTER TABLE job ADD COLUMN capacity_held INTEGER NOT NULL DEFAULT 1;
ALTER TABLE job ADD COLUMN workflow_expected INTEGER NOT NULL DEFAULT 0;
UPDATE job SET capacity_held=0 WHERE status IN ('completed','failed') OR (status='expired' AND cleaned_at IS NOT NULL);
UPDATE job SET workflow_expected=1 WHERE status!='uploading' AND upload_id IS NOT NULL;
CREATE INDEX job_capacity ON job(capacity_held, user_id);
