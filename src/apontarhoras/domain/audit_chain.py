"""Auditoria encadeada: cada registro guarda o selo (SHA-256) do anterior, como uma corrente.

Alterar ou apagar um registro do meio pelo banco quebra a corrente a partir dele. Não há segredo (o código é
público): quem tem acesso ao arquivo e recalcula todos os selos seguintes não é detectado pela corrente sozinha.
Por isso o responsável anota o selo do último registro (tela "Verificar integridade") de tempos em tempos: um selo
anotado fora do banco que deixou de existir também denuncia a alteração, inclusive a exclusão dos últimos registros.
"""

import hashlib
import json
from dataclasses import dataclass
from typing import Any

GENESIS_HASH = "0" * 64  # "selo anterior" do primeiro registro


def canonical_content(
    *,
    at: str,
    actor_id: int | None,
    actor_name: str,
    action: str,
    entity: str,
    entity_id: int | None,
    details: dict[str, Any],
) -> str:
    """Texto estável do registro: mesmos dados → mesmo texto (chaves ordenadas, sem espaços)."""
    return json.dumps(
        [at, actor_id, actor_name, action, entity, entity_id, details],
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )


def chain_hash(prev_hash: str, content: str) -> str:
    """Selo do registro = sha256(selo anterior + conteúdo canônico)."""
    return hashlib.sha256((prev_hash + content).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ChainCheck:
    """Resultado da conferência da corrente."""

    total: int  # registros conferidos
    broken_id: int | None = None  # primeiro registro em que a corrente não confere
    last_id: int | None = None
    last_hash: str | None = None

    @property
    def ok(self) -> bool:
        return self.broken_id is None

    @property
    def short_hash(self) -> str:
        """Começo do selo do último registro, para anotar e comparar depois."""
        return self.last_hash[:16] if self.last_hash else ""
