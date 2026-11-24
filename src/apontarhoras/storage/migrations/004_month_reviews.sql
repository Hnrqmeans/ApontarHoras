-- 004: conferência do mês pelo responsável (D9: o mês não trava; a conferência registra como ele estava).
-- Cada conferência é uma linha (pode conferir de novo; vale a última). `seal` = SHA-256 do conteúdo canônico
-- dos apontamentos do mês naquele momento (domain/report.month_seal).
CREATE TABLE month_reviews (
    id            INTEGER PRIMARY KEY,
    year          INTEGER NOT NULL CHECK (year BETWEEN 2000 AND 2100),
    month         INTEGER NOT NULL CHECK (month BETWEEN 1 AND 12),
    reviewer_id   INTEGER REFERENCES users (id) ON DELETE SET NULL,
    reviewer_name TEXT    NOT NULL,
    reviewed_at   TEXT    NOT NULL,
    entry_count   INTEGER NOT NULL CHECK (entry_count >= 0),
    total_minutes INTEGER NOT NULL CHECK (total_minutes >= 0),
    seal          TEXT    NOT NULL CHECK (length(seal) = 64)
);
CREATE INDEX month_reviews_month ON month_reviews (year, month, id);
