-- 001: usuários, sessões, projetos e auditoria.

CREATE TABLE users (
    id                   INTEGER PRIMARY KEY,
    name                 TEXT    NOT NULL,
    login                TEXT    NOT NULL UNIQUE COLLATE NOCASE,
    password_hash        TEXT    NOT NULL,
    role                 TEXT    NOT NULL CHECK (role IN ('admin', 'colaborador')),
    active               INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
    must_change_password INTEGER NOT NULL DEFAULT 0 CHECK (must_change_password IN (0, 1)),
    failed_attempts      INTEGER NOT NULL DEFAULT 0,
    locked_until         TEXT,
    created_at           TEXT    NOT NULL
);

-- Só o SHA-256 do token fica no banco.
CREATE TABLE sessions (
    token_hash TEXT    PRIMARY KEY,
    user_id    INTEGER NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    created_at TEXT    NOT NULL,
    expires_at TEXT    NOT NULL
);
CREATE INDEX sessions_user ON sessions (user_id);

CREATE TABLE projects (
    id          INTEGER PRIMARY KEY,
    code        TEXT    NOT NULL UNIQUE COLLATE NOCASE,
    name        TEXT    NOT NULL,
    description TEXT    NOT NULL DEFAULT '',
    active      INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
    created_at  TEXT    NOT NULL
);

-- Sem chave estrangeira em actor_id: excluir um usuário não apaga o que ele fez (o nome fica em actor_name).
CREATE TABLE audit_log (
    id         INTEGER PRIMARY KEY,
    at         TEXT    NOT NULL,
    actor_id   INTEGER,
    actor_name TEXT    NOT NULL,
    action     TEXT    NOT NULL,
    entity     TEXT    NOT NULL,
    entity_id  INTEGER,
    details    TEXT    NOT NULL DEFAULT '{}'
);
CREATE INDEX audit_log_at ON audit_log (at);
