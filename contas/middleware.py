from django.shortcuts import redirect
from django.urls import reverse

from contas.utils import IMPERSONAR_KEY


class AcessoMiddleware:
    """Resolve a impersonacao do admin global e faz o roteamento de acesso.

    - Anexa `request.user._perfil_efetivo` quando um admin global esta
      impersonando um usuario (chave na sessao).
    - Usuario autenticado sem perfil -> onboarding (criar organizacao).
    - Admin global sem impersonar -> restrito a area do sistema (/sistema/).
    """

    # Prefixos que qualquer usuario logado pode acessar.
    LIBERADOS = (
        '/accounts/', '/admin/', '/conta/criar-organizacao/',
        '/termos/', '/privacidade/', '/static/', '/media/',
    )
    # Prefixos exclusivos do admin global (nao exigem organizacao).
    ADMIN_PATHS = ('/sistema/',)

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, 'user', None)
        if user is not None and user.is_authenticated:
            self._resolver_impersonacao(request, user)
            resposta = self._rotear(request, user)
            if resposta is not None:
                return resposta
        return self.get_response(request)

    def _resolver_impersonacao(self, request, user):
        from contas.models import PerfilUsuario

        real = getattr(user, 'perfil', None)
        pid = request.session.get(IMPERSONAR_KEY)
        if real and real.eh_admin and pid:
            perfil = (PerfilUsuario.objects
                      .filter(pk=pid)
                      .select_related('organizacao', 'user')
                      .first())
            if perfil is not None:
                user._perfil_efetivo = perfil
            else:
                request.session.pop(IMPERSONAR_KEY, None)

    def _rotear(self, request, user):
        path = request.path
        if any(path.startswith(p) for p in self.LIBERADOS):
            return None

        real = getattr(user, 'perfil', None)
        efetivo = getattr(user, '_perfil_efetivo', None)

        if real is None:
            return redirect(reverse('criar_organizacao'))

        # Admin global sem impersonar so acessa a area do sistema.
        if real.eh_admin and efetivo is None:
            if not any(path.startswith(p) for p in self.ADMIN_PATHS):
                return redirect(reverse('painel_admin'))

        perfil = efetivo or real

        # Paywall: organizacao com assinatura inativa/vencida fica restrita a
        # tela de assinatura (e aos prefixos liberados ja tratados acima). O
        # admin global nunca e travado. Vale para gestor, operador e solicitante.
        if not real.eh_admin:
            org = perfil.organizacao if perfil else None
            if org is not None and not org.assinatura_em_dia():
                if path != reverse('assinatura_vencida'):
                    return redirect(reverse('assinatura_vencida'))
                return None

        # Solicitante so acessa o modulo de pre-agendamento.
        if perfil and perfil.eh_solicitante:
            if not path.startswith('/agendamento/'):
                return redirect(reverse('minhas_solicitacoes'))
        return None
