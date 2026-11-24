-- 002: tarefas (tipo de atividade, define a Lei do Bem), elegibilidade do projeto e apontamentos.

-- Projeto que não é P&D (ex.: "Tarefas internas"): nenhuma hora conta para a Lei do Bem.
ALTER TABLE projects ADD COLUMN rd_eligible INTEGER NOT NULL DEFAULT 1 CHECK (rd_eligible IN (0, 1));

CREATE TABLE tasks (
    id          INTEGER PRIMARY KEY,
    name        TEXT    NOT NULL UNIQUE COLLATE NOCASE,
    rd_eligible INTEGER NOT NULL DEFAULT 1 CHECK (rd_eligible IN (0, 1)),
    active      INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
    created_at  TEXT    NOT NULL
);

-- Tarefas padrão (1 = conta para a Lei do Bem). O responsável pode mudar depois.
INSERT INTO tasks (name, rd_eligible, created_at) VALUES
    ('Desenvolvimento',     1, strftime('%Y-%m-%dT%H:%M:%S+00:00', 'now')),
    ('Documentação',        1, strftime('%Y-%m-%dT%H:%M:%S+00:00', 'now')),
    ('Atualização',         1, strftime('%Y-%m-%dT%H:%M:%S+00:00', 'now')),
    ('Testes e Validações', 1, strftime('%Y-%m-%dT%H:%M:%S+00:00', 'now')),
    ('Reuniões Externas',   1, strftime('%Y-%m-%dT%H:%M:%S+00:00', 'now')),
    ('Manutenção',          0, strftime('%Y-%m-%dT%H:%M:%S+00:00', 'now')),
    ('Suporte',             0, strftime('%Y-%m-%dT%H:%M:%S+00:00', 'now')),
    ('Correções',           0, strftime('%Y-%m-%dT%H:%M:%S+00:00', 'now')),
    ('Reuniões Internas',   0, strftime('%Y-%m-%dT%H:%M:%S+00:00', 'now'));

-- Usuário, projeto e tarefa com horas não podem ser excluídos (RESTRICT): só desativados.
-- Horários em minutos desde 00:00; `minutes` = término − início − intervalo.
CREATE TABLE time_entries (
    id            INTEGER PRIMARY KEY,
    user_id       INTEGER NOT NULL REFERENCES users (id) ON DELETE RESTRICT,
    work_date     TEXT    NOT NULL,
    project_id    INTEGER NOT NULL REFERENCES projects (id) ON DELETE RESTRICT,
    task_id       INTEGER NOT NULL REFERENCES tasks (id) ON DELETE RESTRICT,
    start_minute  INTEGER NOT NULL CHECK (start_minute BETWEEN 0 AND 1439),
    end_minute    INTEGER NOT NULL CHECK (end_minute BETWEEN 1 AND 1439 AND end_minute > start_minute),
    break_minutes INTEGER NOT NULL DEFAULT 0 CHECK (break_minutes >= 0),
    minutes       INTEGER NOT NULL CHECK (minutes > 0),
    rd_eligible   INTEGER NOT NULL CHECK (rd_eligible IN (0, 1)),
    description   TEXT    NOT NULL DEFAULT '',
    created_at    TEXT    NOT NULL,
    updated_at    TEXT    NOT NULL
);
CREATE INDEX time_entries_user_date ON time_entries (user_id, work_date);
CREATE INDEX time_entries_date ON time_entries (work_date);
CREATE INDEX time_entries_project ON time_entries (project_id);
CREATE INDEX time_entries_task ON time_entries (task_id);
