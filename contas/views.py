from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.db import models, transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django.views.decorators.http import require_POST

from contas.forms import (
    ConvidarUsuarioForm,
    CriarOrganizacaoForm,
    PapelForm,
    SignupForm,
)
from contas.models import Organizacao, PerfilUsuario, Plano
from contas.utils import (
    IMPERSONAR_KEY,
    esta_impersonando,
    exige_admin_global,
    exige_gestor,
    organizacao_do,
    perfil_do,
    perfil_real_do,
)


def _plano_padrao():
    plano, _ = Plano.objects.get_or_create(
        slug='padrao',
        defaults={'nome': 'Padrão', 'preco_mensal': 0, 'limite_veiculos': 0},
    )
    return plano


def _smtp_configurado():
    """True se o backend de e-mail eh SMTP (em producao). Em dev/console, False."""
    return 'smtp' in getattr(settings, 'EMAIL_BACKEND', '').lower()


def link_definir_senha(request, user):
    """Monta a URL absoluta para o usuario definir a propria senha (reaproveita
    o fluxo de reset de senha do Django, funciona com senha inutilizavel)."""
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    caminho = reverse('password_reset_confirm',
                      kwargs={'uidb64': uid, 'token': token})
    return request.build_absolute_uri(caminho)


def enviar_convite(user, link):
    """Envia por e-mail o link de definicao de senha. Nao levanta excecao
    (fail_silently) para nao quebrar o cadastro caso o SMTP falhe; o link
    tambem eh exibido na tela como garantia."""
    return send_mail(
        subject='Convite para o Gestão de Frotas',
        message=(
            'Olá,\n\n'
            'Você foi convidado para acessar o Gestão de Frotas.\n'
            'Defina sua senha de acesso pelo link abaixo:\n\n'
            f'{link}\n\n'
            'Se você não esperava este convite, ignore este e-mail.\n\n'
            'Equipe Gestão de Frotas'
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=True,
    )


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
                user=user, organizacao=org, papel=PerfilUsuario.PAPEL_GESTOR)
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
            user=request.user, organizacao=org, papel=PerfilUsuario.PAPEL_GESTOR)
        messages.success(request, 'Organização criada com sucesso!')
        return redirect('home')
    return render(request, 'contas/criar_organizacao.html', {'form': form})


@login_required
@exige_gestor
def usuarios(request):
    org = organizacao_do(request.user)
    form = ConvidarUsuarioForm(request.POST or None, organizacao=org)
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
            # Operador: liga o login ao motorista selecionado.
            motorista = form.cleaned_data.get('motorista')
            if motorista is not None:
                motorista.user = novo
                motorista.save(update_fields=['user'])

        # Gera o link de definicao de senha e tenta enviar por e-mail. O link
        # tambem fica visivel na tela (garante o convite mesmo sem SMTP).
        link = link_definir_senha(request, novo)
        enviar_convite(novo, link)
        request.session['convite'] = {
            'email': novo.email, 'link': link, 'smtp': _smtp_configurado(),
        }
        if _smtp_configurado():
            messages.success(
                request,
                f'Usuário adicionado. Enviamos um e-mail para {novo.email} '
                'definir a senha (o link também aparece abaixo).')
        else:
            messages.success(
                request,
                'Usuário adicionado. Copie o link abaixo e envie para ele '
                'definir a senha.')
        return redirect('usuarios')

    convite = request.session.pop('convite', None)
    membros = PerfilUsuario.objects.filter(organizacao=org).select_related('user')
    return render(request, 'contas/usuarios.html',
                  {'form': form, 'membros': membros,
                   'perfil': perfil_do(request.user), 'convite': convite})


@login_required
@exige_gestor
def alterar_papel(request, perfil_id):
    org = organizacao_do(request.user)
    membro = get_object_or_404(PerfilUsuario, id=perfil_id, organizacao=org)
    if request.method == 'POST':
        form = PapelForm(request.POST)
        if form.is_valid():
            novo_papel = form.cleaned_data['papel']
            if (novo_papel == PerfilUsuario.PAPEL_OPERADOR
                    and not hasattr(membro.user, 'motorista')):
                messages.error(
                    request,
                    'Para ser operador, o usuário precisa estar vinculado a um '
                    'motorista. Vincule-o em Motoristas antes.')
            else:
                membro.papel = novo_papel
                membro.save()
                messages.success(request, 'Papel atualizado.')
    return redirect('usuarios')


@login_required
@exige_gestor
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
@exige_gestor
def conta(request):
    org = organizacao_do(request.user)
    planos = Plano.objects.filter(ativo=True)
    return render(request, 'contas/conta.html',
                  {'org': org, 'planos': planos, 'perfil': perfil_do(request.user)})


def termos(request):
    return render(request, 'contas/termos.html')


def privacidade(request):
    return render(request, 'contas/privacidade.html')


# ---------------------------------------------------------------------------
# Administrador global do sistema
# ---------------------------------------------------------------------------

ACOES_LOG = {0: 'Criação', 1: 'Alteração', 2: 'Exclusão', 3: 'Acesso'}


@login_required
@exige_admin_global
def painel_admin(request):
    """Painel do admin global: apenas contagens agregadas (sem dados sensiveis
    das organizacoes) e a lista de organizacoes para impersonar."""
    from carro.models import Motorista, Veiculo

    orgs = (
        Organizacao.objects.annotate(
            n_veiculos=models.Count('veiculos', distinct=True),
            n_perfis=models.Count('perfis', distinct=True),
            n_motoristas=models.Count('motoristas', distinct=True),
        ).order_by('nome')
    )
    context = {
        'total_orgs': Organizacao.objects.count(),
        'total_veiculos': Veiculo.objects.count(),
        'total_motoristas': Motorista.objects.count(),
        'total_usuarios': PerfilUsuario.objects.count(),
        'orgs': orgs,
    }
    return render(request, 'contas/painel_admin.html', context)


@login_required
@exige_admin_global
def admin_organizacao(request, org_id):
    """Hub de administracao de uma organizacao: usuarios e veiculos (CRUD),
    alem de impersonar para testes."""
    from carro.models import Veiculo
    org = get_object_or_404(Organizacao, id=org_id)
    perfis = PerfilUsuario.objects.filter(organizacao=org).select_related('user')
    veiculos = Veiculo.objects.filter(organizacao=org)
    convite = request.session.pop('convite', None)
    return render(request, 'contas/admin_organizacao.html',
                  {'org': org, 'perfis': perfis, 'veiculos': veiculos,
                   'convite': convite})


@login_required
@exige_admin_global
@require_POST
def impersonar(request, perfil_id):
    perfil = get_object_or_404(
        PerfilUsuario.objects.exclude(papel=PerfilUsuario.PAPEL_ADMIN),
        id=perfil_id)
    request.session[IMPERSONAR_KEY] = perfil.id
    messages.info(
        request,
        f'Você está navegando como {perfil.user.get_username()} '
        f'({perfil.get_papel_display()}). Use "Sair da simulação" para voltar.')
    return redirect('home')


@login_required
@require_POST
def sair_impersonacao(request):
    request.session.pop(IMPERSONAR_KEY, None)
    messages.success(request, 'Você voltou ao painel do administrador.')
    return redirect('painel_admin')


def _logs_qs(organizacao=None):
    from auditlog.models import LogEntry
    qs = LogEntry.objects.select_related('actor', 'content_type').order_by('-timestamp')
    if organizacao is not None:
        # Registros feitos por usuarios da organizacao.
        qs = qs.filter(actor__perfil__organizacao=organizacao)
    return qs


def _monta_logs(qs, limite=200):
    logs = []
    for e in qs[:limite]:
        logs.append({
            'quando': e.timestamp,
            'login': e.actor.get_username() if e.actor else '—',
            'acao': ACOES_LOG.get(e.action, str(e.action)),
            'tipo': e.content_type.name if e.content_type else '',
            'objeto': e.object_repr,
        })
    return logs


@login_required
@exige_gestor
def logs(request):
    """Registro de alteracoes da organizacao (login, data/hora, tipo)."""
    org = organizacao_do(request.user)
    return render(request, 'contas/logs.html', {
        'logs': _monta_logs(_logs_qs(org)),
        'escopo': f'Organização · {org.nome}' if org else 'Organização',
    })


@login_required
@exige_admin_global
def logs_sistema(request):
    """Registro de alteracoes de todo o sistema (admin global)."""
    return render(request, 'contas/logs.html', {
        'logs': _monta_logs(_logs_qs()),
        'escopo': 'Todo o sistema',
        'do_sistema': True,
    })


# ---- CRUD de organizacoes (admin global) ----

@login_required
@exige_admin_global
def nova_organizacao(request):
    from contas.forms import OrganizacaoAdminForm
    form = OrganizacaoAdminForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        org = form.save(commit=False)
        if org.plano is None:
            org.plano = _plano_padrao()
        org.save()
        messages.success(request, 'Organização criada.')
        return redirect('admin_organizacao', org_id=org.id)
    return render(request, 'contas/sistema_form.html',
                  {'form': form, 'titulo': 'Nova organização',
                   'voltar': reverse('painel_admin')})


@login_required
@exige_admin_global
def editar_organizacao(request, org_id):
    from contas.forms import OrganizacaoAdminForm
    org = get_object_or_404(Organizacao, id=org_id)
    form = OrganizacaoAdminForm(request.POST or None, instance=org)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Organização atualizada.')
        return redirect('admin_organizacao', org_id=org.id)
    return render(request, 'contas/sistema_form.html',
                  {'form': form, 'titulo': f'Editar {org.nome}',
                   'voltar': reverse('admin_organizacao', args=[org.id])})


@login_required
@exige_admin_global
@require_POST
def excluir_organizacao(request, org_id):
    org = get_object_or_404(Organizacao, id=org_id)
    org.delete()  # cascata remove veiculos, motoristas e perfis da org
    messages.success(request, 'Organização excluída.')
    return redirect('painel_admin')


# ---- CRUD de usuarios (admin global) ----

@login_required
@exige_admin_global
def novo_usuario_admin(request, org_id):
    org = get_object_or_404(Organizacao, id=org_id)
    form = ConvidarUsuarioForm(request.POST or None, organizacao=org,
                               incluir_admin=True)
    if request.method == 'POST' and form.is_valid():
        papel = form.cleaned_data['papel']
        with transaction.atomic():
            novo = User.objects.create_user(
                username=form.cleaned_data['username'],
                email=form.cleaned_data['email'])
            novo.set_unusable_password()
            if papel == PerfilUsuario.PAPEL_ADMIN:
                novo.is_staff = novo.is_superuser = True
            novo.save()
            PerfilUsuario.objects.create(
                user=novo,
                organizacao=None if papel == PerfilUsuario.PAPEL_ADMIN else org,
                papel=papel)
            motorista = form.cleaned_data.get('motorista')
            if motorista is not None:
                motorista.user = novo
                motorista.save(update_fields=['user'])
        link = link_definir_senha(request, novo)
        enviar_convite(novo, link)
        request.session['convite'] = {
            'email': novo.email, 'link': link, 'smtp': _smtp_configurado()}
        messages.success(request, 'Usuário criado. O link para definir senha está abaixo.')
        return redirect('admin_organizacao', org_id=org.id)
    return render(request, 'contas/sistema_form.html',
                  {'form': form, 'titulo': f'Novo usuário · {org.nome}',
                   'voltar': reverse('admin_organizacao', args=[org.id])})


@login_required
@exige_admin_global
def editar_usuario_admin(request, perfil_id):
    from contas.forms import PapelAdminForm
    perfil = get_object_or_404(
        PerfilUsuario.objects.select_related('user', 'organizacao'), id=perfil_id)
    if request.method == 'POST':
        form = PapelAdminForm(request.POST)
        if form.is_valid():
            novo_papel = form.cleaned_data['papel']
            if (novo_papel == PerfilUsuario.PAPEL_OPERADOR
                    and not hasattr(perfil.user, 'motorista')):
                messages.error(request, 'Operador precisa estar vinculado a um motorista.')
                destino = perfil.organizacao_id
                return (redirect('admin_organizacao', org_id=destino)
                        if destino else redirect('painel_admin'))
            perfil.papel = novo_papel
            if novo_papel == PerfilUsuario.PAPEL_ADMIN:
                perfil.organizacao = None
            perfil.save()
            perfil.user.is_active = form.cleaned_data['ativo']
            perfil.user.save(update_fields=['is_active'])
            messages.success(request, 'Usuário atualizado.')
            destino = perfil.organizacao_id
            return (redirect('admin_organizacao', org_id=destino)
                    if destino else redirect('painel_admin'))
    form = PapelAdminForm(initial={'papel': perfil.papel,
                                   'ativo': perfil.user.is_active})
    voltar = (reverse('admin_organizacao', args=[perfil.organizacao_id])
              if perfil.organizacao_id else reverse('painel_admin'))
    return render(request, 'contas/sistema_form.html',
                  {'form': form, 'titulo': f'Editar {perfil.user.get_username()}',
                   'voltar': voltar})


@login_required
@exige_admin_global
@require_POST
def excluir_usuario_admin(request, perfil_id):
    perfil = get_object_or_404(PerfilUsuario, id=perfil_id)
    if perfil.user_id == request.user.id:
        messages.error(request, 'Você não pode excluir a si mesmo.')
        return redirect('painel_admin')
    org_id = perfil.organizacao_id
    perfil.user.delete()  # cascata remove o perfil
    messages.success(request, 'Usuário excluído.')
    return redirect('admin_organizacao', org_id=org_id) if org_id else redirect('painel_admin')


# ---- CRUD de veiculos (admin global) ----

@login_required
@exige_admin_global
def novo_veiculo_admin(request, org_id):
    from carro.forms import VeiculoForm
    org = get_object_or_404(Organizacao, id=org_id)
    form = VeiculoForm(request.POST or None, request.FILES or None, organizacao=org)
    if request.method == 'POST' and form.is_valid():
        veiculo = form.save(commit=False)
        veiculo.organizacao = org
        veiculo.save()
        messages.success(request, 'Veículo criado.')
        return redirect('admin_organizacao', org_id=org.id)
    return render(request, 'contas/sistema_form.html',
                  {'form': form, 'titulo': f'Novo veículo · {org.nome}',
                   'voltar': reverse('admin_organizacao', args=[org.id]),
                   'multipart': True})


@login_required
@exige_admin_global
def editar_veiculo_admin(request, veiculo_id):
    from carro.forms import VeiculoForm
    from carro.models import Veiculo
    veiculo = get_object_or_404(Veiculo, id=veiculo_id)
    form = VeiculoForm(request.POST or None, request.FILES or None,
                       instance=veiculo, organizacao=veiculo.organizacao)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Veículo atualizado.')
        return redirect('admin_organizacao', org_id=veiculo.organizacao_id)
    return render(request, 'contas/sistema_form.html',
                  {'form': form, 'titulo': f'Editar {veiculo}',
                   'voltar': reverse('admin_organizacao', args=[veiculo.organizacao_id]),
                   'multipart': True})


@login_required
@exige_admin_global
@require_POST
def excluir_veiculo_admin(request, veiculo_id):
    from carro.models import Veiculo
    veiculo = get_object_or_404(Veiculo, id=veiculo_id)
    org_id = veiculo.organizacao_id
    veiculo.delete()
    messages.success(request, 'Veículo excluído.')
    return redirect('admin_organizacao', org_id=org_id)
