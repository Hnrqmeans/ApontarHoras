-- 005: feriados (dia sem jornada esperada). Cadastro do responsável; um registro por data.
CREATE TABLE holidays (
    id          INTEGER PRIMARY KEY,
    day         TEXT    NOT NULL UNIQUE,
    description TEXT    NOT NULL,
    created_at  TEXT    NOT NULL
);
