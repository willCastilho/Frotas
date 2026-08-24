from contas.utils import esta_impersonando, perfil_do, perfil_real_do


def rbac(request):
    """Expoe o perfil efetivo (considerando impersonacao) para os templates."""
    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated:
        return {}
    return {
        'perfil_efetivo': perfil_do(user),
        'perfil_real': perfil_real_do(user),
        'impersonando': esta_impersonando(user),
    }
