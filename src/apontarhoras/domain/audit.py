"""Registro de auditoria: quem fez o quê, quando."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any

ACTION_LABELS = {
    "setup": "Primeiro acesso",
    "login": "Entrou",
    "login_failed": "Senha errada",
    "locked": "Bloqueado por tentativas",
    "create": "Criou",
    "update": "Alterou",
    "delete": "Excluiu",
    "password_change": "Trocou a senha",
    "password_reset": "Redefiniu a senha",
    "review": "Conferiu",
    "export": "Exportou",
}

ENTITY_LABELS = {
    "user": "Usuário",
    "project": "Projeto",
    "task": "Tarefa",
    "time_entry": "Apontamento",
    "month_review": "Conferência do mês",
    "report": "Relatório",
}


@dataclass(frozen=True)
class AuditEntry:
    id: int
    at: datetime
    actor_id: int | None
    actor_name: str
    action: str
    entity: str
    entity_id: int | None
    details: dict[str, Any]

    @property
    def action_label(self) -> str:
        return ACTION_LABELS.get(self.action, self.action)

    @property
    def entity_label(self) -> str:
        return ENTITY_LABELS.get(self.entity, self.entity)


def changes(before: dict[str, Any], after: dict[str, Any]) -> dict[str, list[Any]]:
    """Só os campos que mudaram: {"nome": [antes, depois]}."""
    return {key: [before.get(key), value] for key, value in after.items() if before.get(key) != value}
