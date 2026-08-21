"""Helpers de multi-tenancy: obter a organizacao do usuario logado."""
from functools import wraps

from django.contrib import messages
from django.shortcuts import redirect


def organizacao_do(user):
    """Retorna a Organizacao do usuario (via perfil) ou None."""
    perfil = getattr(user, 'perfil', None)
    return perfil.organizacao if perfil else None


def perfil_do(user):
    return getattr(user, 'perfil', None)


def exige_escrita(view):
    """Bloqueia a acao se o usuario nao tiver papel de escrita."""
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        perfil = perfil_do(request.user)
        if not perfil or not perfil.pode_escrever:
            messages.error(request, 'Você não tem permissão para esta ação.')
            return redirect('home')
        return view(request, *args, **kwargs)
    return wrapper


def exige_admin(view):
    """Bloqueia a acao se o usuario nao administrar a organizacao."""
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        perfil = perfil_do(request.user)
        if not perfil or not perfil.pode_administrar:
            messages.error(request, 'Apenas administradores da conta podem fazer isso.')
            return redirect('home')
        return view(request, *args, **kwargs)
    return wrapper
