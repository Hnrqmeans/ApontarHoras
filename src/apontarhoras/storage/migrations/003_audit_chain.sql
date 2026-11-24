-- 003: auditoria encadeada. Cada registro guarda o selo do anterior (prev_hash) e o próprio (hash).
-- O SQLite não calcula SHA-256: os registros que já existiam são selados pelo programa ao abrir o banco
-- (storage/audit_repo.seal_pending); os novos já entram selados (audit_repo.insert).

ALTER TABLE audit_log ADD COLUMN prev_hash TEXT;
ALTER TABLE audit_log ADD COLUMN hash TEXT;
