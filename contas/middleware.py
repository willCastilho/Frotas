from django.shortcuts import redirect
from django.urls import reverse


# Prefixos de URL que um usuario logado SEM organizacao ainda pode acessar.
_LIBERADOS = (
    '/accounts/',
    '/admin/',
    '/conta/criar-organizacao/',
    '/conta/sair/',
    '/termos/',
    '/privacidade/',
    '/static/',
    '/media/',
)


class OrganizacaoObrigatoriaMiddleware:
    """Se um usuario autenticado nao tem organizacao (perfil), redireciona para
    a criacao de organizacao. Garante o isolamento multi-tenant: nenhuma tela do
    sistema e acessada sem uma organizacao associada."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, 'user', None)
        if user is not None and user.is_authenticated:
            tem_org = hasattr(user, 'perfil')
            liberado = any(request.path.startswith(p) for p in _LIBERADOS)
            if not tem_org and not liberado:
                return redirect(reverse('criar_organizacao'))
        return self.get_response(request)
