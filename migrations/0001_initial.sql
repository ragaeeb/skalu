CREATE TABLE user (id TEXT PRIMARY KEY, name TEXT NOT NULL, email TEXT NOT NULL UNIQUE, email_verified INTEGER NOT NULL, image TEXT, created_at INTEGER NOT NULL, updated_at INTEGER NOT NULL);
CREATE TABLE session (id TEXT PRIMARY KEY, token TEXT NOT NULL UNIQUE, user_id TEXT NOT NULL REFERENCES user(id) ON DELETE CASCADE, expires_at INTEGER NOT NULL, created_at INTEGER NOT NULL, updated_at INTEGER NOT NULL, ip_address TEXT, user_agent TEXT);
CREATE INDEX session_user ON session(user_id);
CREATE TABLE account (id TEXT PRIMARY KEY, account_id TEXT NOT NULL, provider_id TEXT NOT NULL, user_id TEXT NOT NULL REFERENCES user(id) ON DELETE CASCADE, access_token TEXT, refresh_token TEXT, id_token TEXT, access_token_expires_at INTEGER, refresh_token_expires_at INTEGER, scope TEXT, password TEXT, created_at INTEGER NOT NULL, updated_at INTEGER NOT NULL);
CREATE INDEX account_user ON account(user_id);
CREATE TABLE verification (id TEXT PRIMARY KEY, identifier TEXT NOT NULL, value TEXT NOT NULL, expires_at INTEGER NOT NULL, created_at INTEGER NOT NULL, updated_at INTEGER NOT NULL);
CREATE INDEX verification_identifier ON verification(identifier);
CREATE TABLE rate_limit (id TEXT PRIMARY KEY, key TEXT NOT NULL UNIQUE, count INTEGER NOT NULL, last_request INTEGER NOT NULL);
CREATE TABLE api_key (user_id TEXT PRIMARY KEY REFERENCES user(id) ON DELETE CASCADE, hash TEXT NOT NULL UNIQUE, prefix TEXT NOT NULL, created_at INTEGER NOT NULL);
CREATE TABLE job (
    id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES user(id), filename TEXT NOT NULL,
    size INTEGER NOT NULL, status TEXT NOT NULL, upload_id TEXT, params TEXT NOT NULL,
    total INTEGER NOT NULL DEFAULT 0, error TEXT, dpi TEXT, engine_version TEXT,
    created_at INTEGER NOT NULL, expires_at INTEGER NOT NULL, cleaned_at INTEGER
);
CREATE INDEX job_user_created ON job(user_id, created_at);
CREATE INDEX job_status_expiry ON job(status, expires_at);
CREATE TABLE upload_part (job_id TEXT NOT NULL REFERENCES job(id) ON DELETE CASCADE, part INTEGER NOT NULL, etag TEXT NOT NULL, size INTEGER NOT NULL, PRIMARY KEY(job_id, part));
CREATE TABLE page (job_id TEXT NOT NULL REFERENCES job(id) ON DELETE CASCADE, page INTEGER NOT NULL, PRIMARY KEY(job_id, page));
