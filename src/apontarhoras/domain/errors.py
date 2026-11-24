"""Erros com mensagem pronta para mostrar ao usuário (pt-BR)."""


class AppError(Exception):
    """Base: `str(erro)` é a mensagem para a tela."""


class ValidationError(AppError):
    """Dado informado é inválido."""


class PermissionDenied(AppError):
    """O usuário logado não pode fazer esta operação."""


class NotFound(AppError):
    """Registro não existe (ou foi excluído)."""


class AuthError(AppError):
    """Falha de login (usuário/senha inválidos, bloqueado, desativado)."""
