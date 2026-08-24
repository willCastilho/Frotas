"""Helpers de RBAC e multi-tenancy.

O admin global pode "impersonar" um usuario: nesse caso o perfil EFETIVO
(usado para organizacao e permissoes) e o do usuario impersonado, mas a
identidade real (para logs e para encerrar a impersonacao) continua sendo a do
admin. A impersonacao vive na sessao e e resolvida pelo AcessoMiddleware, que
anexa `request.user._perfil_efetivo`.
"""
from functools import wraps

from django.contrib import messages
from django.shortcuts import redirect

IMPERSONAR_KEY = 'impersonar_perfil_id'


def perfil_real_do(user):
    """Perfil real do usuario logado, ignorando impersonacao."""
    return getattr(user, 'perfil', None)


def perfil_do(user):
    """Perfil EFETIVO: o impersonado (se houver) ou o real."""
    efetivo = getattr(user, '_perfil_efetivo', None)
    return efetivo if efetivo is not None else perfil_real_do(user)


def organizacao_do(user):
    perfil = perfil_do(user)
    return perfil.organizacao if perfil else None


def esta_impersonando(user):
    return getattr(user, '_perfil_efetivo', None) is not None


def veiculo_do_operador(user):
    """Veiculo atualmente atribuido ao operador (via motorista vinculado ao
    perfil efetivo). None se nao houver motorista ou vinculo em aberto."""
    perfil = perfil_do(user)
    if not perfil or not perfil.eh_operador:
        return None
    motorista = getattr(perfil.user, 'motorista', None)
    return motorista.veiculo_atual() if motorista else None


def pode_lancar_no_veiculo(user, veiculo):
    """True se o usuario pode lancar dados (custo/abastecimento/km) no veiculo:
    o gestor da organizacao do veiculo, ou o operador dono do veiculo."""
    perfil = perfil_do(user)
    if not perfil:
        return False
    if perfil.eh_gestor and veiculo.organizacao_id == perfil.organizacao_id:
        return True
    if perfil.eh_operador:
        v = veiculo_do_operador(user)
        return v is not None and v.id == veiculo.id
    return False


def exige_gestor(view):
    """Restringe a acao ao gestor da organizacao (administracao da conta)."""
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        perfil = perfil_do(request.user)
        if not perfil or not perfil.pode_administrar:
            messages.error(request, 'Apenas o gestor da organização pode fazer isso.')
            return redirect('home')
        return view(request, *args, **kwargs)
    return wrapper


def exige_admin_global(view):
    """Restringe a area ao administrador global do sistema (identidade real)."""
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        perfil = perfil_real_do(request.user)
        if not perfil or not perfil.eh_admin:
            messages.error(request, 'Área exclusiva do administrador do sistema.')
            return redirect('home')
        return view(request, *args, **kwargs)
    return wrapper


# Compatibilidade: escrita geral na organizacao = gestor.
exige_escrita = exige_gestor
exige_admin = exige_gestor
