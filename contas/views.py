from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordResetForm
from django.contrib.auth.models import User
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render

from contas.forms import (
    ConvidarUsuarioForm,
    CriarOrganizacaoForm,
    PapelForm,
    SignupForm,
)
from contas.models import Organizacao, PerfilUsuario, Plano
from contas.utils import exige_admin, organizacao_do, perfil_do


def _plano_padrao():
    plano, _ = Plano.objects.get_or_create(
        slug='padrao',
        defaults={'nome': 'Padrão', 'preco_mensal': 0, 'limite_veiculos': 0},
    )
    return plano


def cadastro(request):
    """Sign up: cria usuario + organizacao + perfil (admin) e loga."""
    if request.user.is_authenticated:
        return redirect('home')
    form = SignupForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            user = form.save(commit=False)
            user.email = form.cleaned_data['email']
            user.save()
            org = Organizacao.objects.create(
                nome=form.cleaned_data['nome_organizacao'], plano=_plano_padrao())
            PerfilUsuario.objects.create(
                user=user, organizacao=org, papel=PerfilUsuario.PAPEL_ADMIN)
        login(request, user)
        messages.success(request, 'Conta criada com sucesso! Bem-vindo.')
        return redirect('home')
    return render(request, 'registration/signup.html', {'form': form})


@login_required
def criar_organizacao(request):
    """Onboarding para usuario logado sem organizacao (ex.: superusuario)."""
    if hasattr(request.user, 'perfil'):
        return redirect('home')
    form = CriarOrganizacaoForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        org = form.save(commit=False)
        org.plano = _plano_padrao()
        org.save()
        PerfilUsuario.objects.create(
            user=request.user, organizacao=org, papel=PerfilUsuario.PAPEL_ADMIN)
        messages.success(request, 'Organização criada com sucesso!')
        return redirect('home')
    return render(request, 'contas/criar_organizacao.html', {'form': form})


@login_required
@exige_admin
def usuarios(request):
    org = organizacao_do(request.user)
    form = ConvidarUsuarioForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            novo = User.objects.create_user(
                username=form.cleaned_data['username'],
                email=form.cleaned_data['email'],
            )
            novo.set_unusable_password()
            novo.save()
            PerfilUsuario.objects.create(
                user=novo, organizacao=org, papel=form.cleaned_data['papel'])
        # Envia e-mail para o usuario definir a senha (reaproveita o fluxo de reset).
        reset = PasswordResetForm({'email': form.cleaned_data['email']})
        if reset.is_valid():
            reset.save(request=request,
                       use_https=request.is_secure(),
                       email_template_name='registration/password_reset_email.html')
        messages.success(request, 'Usuário adicionado. Enviamos um e-mail para ele definir a senha.')
        return redirect('usuarios')

    membros = PerfilUsuario.objects.filter(organizacao=org).select_related('user')
    return render(request, 'contas/usuarios.html',
                  {'form': form, 'membros': membros, 'perfil': perfil_do(request.user)})


@login_required
@exige_admin
def alterar_papel(request, perfil_id):
    org = organizacao_do(request.user)
    membro = get_object_or_404(PerfilUsuario, id=perfil_id, organizacao=org)
    if request.method == 'POST':
        form = PapelForm(request.POST)
        if form.is_valid():
            membro.papel = form.cleaned_data['papel']
            membro.save()
            messages.success(request, 'Papel atualizado.')
    return redirect('usuarios')


@login_required
@exige_admin
def remover_usuario(request, perfil_id):
    org = organizacao_do(request.user)
    membro = get_object_or_404(PerfilUsuario, id=perfil_id, organizacao=org)
    if membro.user_id == request.user.id:
        messages.error(request, 'Você não pode remover a si mesmo.')
    elif request.method == 'POST':
        membro.user.delete()  # cascata remove o perfil
        messages.success(request, 'Usuário removido.')
    return redirect('usuarios')


@login_required
def conta(request):
    org = organizacao_do(request.user)
    planos = Plano.objects.filter(ativo=True)
    return render(request, 'contas/conta.html',
                  {'org': org, 'planos': planos, 'perfil': perfil_do(request.user)})


def termos(request):
    return render(request, 'contas/termos.html')


def privacidade(request):
    return render(request, 'contas/privacidade.html')
