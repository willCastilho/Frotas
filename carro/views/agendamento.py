"""Modulo de pre-agendamento de veiculos.

Fluxo:
- Solicitante se auto-cadastra por um link com o token da organizacao e fica
  com status 'pendente'; o gestor aprova o cadastro para liberar o acesso.
- Solicitante (aprovado) pede um veiculo informando setor, periodo, destino e
  se precisa de motorista.
- Gestor aprova escolhendo um veiculo livre no periodo (sem conflito de agenda
  e sem documento vencido) e, se necessario, um motorista disponivel; ou recusa.
"""
import calendar as _calendar
from datetime import date, timedelta

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from carro.forms import (
    AprovarSolicitacaoForm,
    DevolucaoForm,
    SolicitacaoForm,
    SolicitanteSignupForm,
)
from carro.models import (
    AtribuicaoVeiculo,
    Solicitante,
    SolicitacaoVeiculo,
    motoristas_disponiveis,
    veiculos_disponiveis,
)
from carro.emails_agendamento import (
    notificar_decisao,
    notificar_gestores_nova_solicitacao,
)
from contas.models import Organizacao, PerfilUsuario
from contas.utils import (
    exige_gestor,
    organizacao_do,
    perfil_do,
    solicitante_do,
)


# --------------------------------------------------------------- auto-cadastro

def cadastro_solicitante(request, token):
    """Auto-cadastro publico de solicitante para uma organizacao (por token)."""
    org = Organizacao.objects.filter(token_convite=token).first()
    if org is None:
        return render(request, 'agendamento/cadastro_invalido.html', status=404)
    if request.user.is_authenticated:
        return redirect('home')

    form = SolicitanteSignupForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        dados = form.cleaned_data
        with transaction.atomic():
            user = User.objects.create_user(
                username=dados['username'], email=dados['email'],
                password=dados['password1'])
            PerfilUsuario.objects.create(
                user=user, organizacao=org,
                papel=PerfilUsuario.PAPEL_SOLICITANTE)
            Solicitante.objects.create(
                organizacao=org, user=user, nome=dados['nome'],
                setor=dados['setor'], cpf=dados.get('cpf', ''),
                cnh=dados.get('cnh', ''),
                cnh_categoria=dados.get('cnh_categoria', ''),
                cnh_validade=dados.get('cnh_validade'),
                telefone=dados.get('telefone', ''), email=dados['email'],
                status=Solicitante.STATUS_PENDENTE)
        login(request, user)
        messages.success(
            request, 'Cadastro enviado! Aguarde a aprovação do gestor de frotas.')
        return redirect('minhas_solicitacoes')
    return render(request, 'agendamento/cadastro_solicitante.html',
                  {'form': form, 'org': org})


# ----------------------------------------------------------------- solicitante

@login_required
def minhas_solicitacoes(request):
    solicitante = solicitante_do(request.user)
    if solicitante is None:
        messages.error(request, 'Área exclusiva de solicitantes.')
        return redirect('home')
    solicitacoes = solicitante.solicitacoes.select_related(
        'veiculo', 'motorista').all()
    return render(request, 'agendamento/minhas_solicitacoes.html', {
        'solicitante': solicitante,
        'solicitacoes': solicitacoes,
    })


@login_required
def nova_solicitacao(request):
    solicitante = solicitante_do(request.user)
    if solicitante is None:
        messages.error(request, 'Área exclusiva de solicitantes.')
        return redirect('home')
    if not solicitante.aprovado:
        messages.error(
            request, 'Seu cadastro ainda está em aprovação; você poderá '
            'solicitar veículos assim que o gestor liberar.')
        return redirect('minhas_solicitacoes')

    # Trava: nao pode pedir outro veiculo com devolucao pendente.
    pendente = solicitante.devolucao_pendente()
    if pendente:
        messages.error(
            request, 'Você tem um veículo a devolver '
            f'({pendente.veiculo} · retorno previsto '
            f'{pendente.retorno_previsto:%d/%m/%Y %H:%M}). Registre a '
            'devolução antes de solicitar outro.')
        return redirect('minhas_solicitacoes')

    form = SolicitacaoForm(request.POST or None,
                           initial={'setor': solicitante.setor})
    if request.method == 'POST' and form.is_valid():
        sol = form.save(commit=False)
        sol.solicitante = solicitante
        sol.organizacao = solicitante.organizacao
        sol.status = SolicitacaoVeiculo.STATUS_PENDENTE
        sol.save()
        notificar_gestores_nova_solicitacao(sol)
        messages.success(
            request, 'Solicitação enviada! Aguarde a aprovação do gestor.')
        return redirect('minhas_solicitacoes')
    return render(request, 'agendamento/nova_solicitacao.html', {'form': form})


@login_required
@require_POST
def cancelar_solicitacao(request, pk):
    solicitante = solicitante_do(request.user)
    if solicitante is None:
        return redirect('home')
    sol = get_object_or_404(
        SolicitacaoVeiculo, pk=pk, solicitante=solicitante)
    if sol.status in (SolicitacaoVeiculo.STATUS_PENDENTE,
                      SolicitacaoVeiculo.STATUS_APROVADA):
        sol.status = SolicitacaoVeiculo.STATUS_CANCELADA
        sol.save(update_fields=['status', 'atualizado_em'])
        messages.success(request, 'Solicitação cancelada.')
    else:
        messages.error(request, 'Esta solicitação não pode ser cancelada.')
    return redirect('minhas_solicitacoes')


@login_required
@require_POST
def iniciar_uso(request, pk):
    solicitante = solicitante_do(request.user)
    if solicitante is None:
        return redirect('home')
    sol = get_object_or_404(
        SolicitacaoVeiculo, pk=pk, solicitante=solicitante)
    if sol.status == SolicitacaoVeiculo.STATUS_APROVADA:
        sol.iniciar_uso()
        messages.success(request, 'Retirada registrada. Bom uso!')
    else:
        messages.error(request, 'Só é possível retirar uma reserva aprovada.')
    return redirect('minhas_solicitacoes')


@login_required
def registrar_devolucao(request, pk):
    solicitante = solicitante_do(request.user)
    if solicitante is None:
        messages.error(request, 'Área exclusiva de solicitantes.')
        return redirect('home')
    sol = get_object_or_404(
        SolicitacaoVeiculo, pk=pk, solicitante=solicitante)
    if sol.status not in (SolicitacaoVeiculo.STATUS_APROVADA,
                          SolicitacaoVeiculo.STATUS_EM_USO):
        messages.error(request, 'Esta solicitação não está em uso.')
        return redirect('minhas_solicitacoes')

    km_minimo = sol.veiculo.km_atual() if sol.veiculo else None
    form = DevolucaoForm(
        request.POST or None, km_minimo=km_minimo,
        initial={'retorno_real': timezone.now().strftime('%Y-%m-%dT%H:%M')})
    if request.method == 'POST' and form.is_valid():
        sol.registrar_devolucao(
            retorno_real=form.cleaned_data['retorno_real'],
            km_final=form.cleaned_data['km_final'],
            observacao=form.cleaned_data.get('obs_devolucao', ''))
        messages.success(
            request, 'Devolução registrada. Obrigado! O odômetro do veículo '
            'foi atualizado.')
        return redirect('minhas_solicitacoes')
    return render(request, 'agendamento/devolucao.html',
                  {'form': form, 'sol': sol})


# ---------------------------------------------------------------------- gestor

@login_required
@exige_gestor
def solicitacoes_gestor(request):
    org = organizacao_do(request.user)
    status = request.GET.get('status', 'pendente')
    qs = (SolicitacaoVeiculo.objects
          .filter(organizacao=org)
          .select_related('solicitante', 'veiculo', 'motorista'))
    if status in dict(SolicitacaoVeiculo.STATUS_CHOICES):
        qs = qs.filter(status=status)
    pendentes_cadastro = Solicitante.objects.filter(
        organizacao=org, status=Solicitante.STATUS_PENDENTE).count()
    return render(request, 'agendamento/gestor_solicitacoes.html', {
        'solicitacoes': qs,
        'status': status,
        'status_choices': SolicitacaoVeiculo.STATUS_CHOICES,
        'pendentes_cadastro': pendentes_cadastro,
    })


@login_required
@exige_gestor
def aprovar_solicitacao(request, pk):
    org = organizacao_do(request.user)
    sol = get_object_or_404(
        SolicitacaoVeiculo, pk=pk, organizacao=org)
    if sol.status != SolicitacaoVeiculo.STATUS_PENDENTE:
        messages.error(request, 'Esta solicitação já foi decidida.')
        return redirect('solicitacoes_gestor')

    veiculos = veiculos_disponiveis(org, sol.saida_prevista, sol.retorno_previsto)
    motoristas = motoristas_disponiveis(
        org, sol.saida_prevista, sol.retorno_previsto)
    # ModelChoiceField precisa de queryset; convertemos as listas em querysets.
    from carro.models import Motorista, Veiculo
    veic_qs = Veiculo.objects.filter(id__in=[v.id for v in veiculos])
    mot_qs = Motorista.objects.filter(id__in=[m.id for m in motoristas])

    form = AprovarSolicitacaoForm(
        request.POST or None, veiculos=veic_qs, motoristas=mot_qs,
        precisa_motorista=sol.precisa_motorista)

    if request.method == 'POST' and form.is_valid():
        veiculo = form.cleaned_data['veiculo']
        motorista = form.cleaned_data.get('motorista')
        # Revalida o conflito no momento de gravar (evita corrida).
        livres_ids = {v.id for v in veiculos_disponiveis(
            org, sol.saida_prevista, sol.retorno_previsto)}
        if veiculo.id not in livres_ids:
            messages.error(
                request, 'Este veículo deixou de estar disponível no período. '
                'Escolha outro.')
            return redirect('aprovar_solicitacao', pk=sol.pk)

        with transaction.atomic():
            sol.veiculo = veiculo
            sol.motorista = motorista
            sol.status = SolicitacaoVeiculo.STATUS_APROVADA
            sol.aprovado_por = request.user
            sol.data_decisao = timezone.now()
            sol.motivo_recusa = ''
            if motorista:
                atrib = AtribuicaoVeiculo.objects.create(
                    veiculo=veiculo, motorista=motorista,
                    data_inicio=sol.saida_prevista.date(),
                    data_fim=sol.retorno_previsto.date(),
                    observacao=f'Agendamento #{sol.pk} · {sol.destino}'[:200])
                sol.atribuicao = atrib
            sol.save()
        notificar_decisao(sol)
        messages.success(request, 'Solicitação aprovada e veículo reservado.')
        return redirect('solicitacoes_gestor')

    return render(request, 'agendamento/aprovar_solicitacao.html', {
        'sol': sol,
        'form': form,
        'sem_veiculo': not veiculos,
    })


@login_required
@exige_gestor
@require_POST
def recusar_solicitacao(request, pk):
    org = organizacao_do(request.user)
    sol = get_object_or_404(SolicitacaoVeiculo, pk=pk, organizacao=org)
    if sol.status != SolicitacaoVeiculo.STATUS_PENDENTE:
        messages.error(request, 'Esta solicitação já foi decidida.')
        return redirect('solicitacoes_gestor')
    sol.status = SolicitacaoVeiculo.STATUS_RECUSADA
    sol.motivo_recusa = (request.POST.get('motivo') or '').strip()[:200]
    sol.aprovado_por = request.user
    sol.data_decisao = timezone.now()
    sol.save()
    notificar_decisao(sol)
    messages.success(request, 'Solicitação recusada.')
    return redirect('solicitacoes_gestor')


@login_required
@exige_gestor
def cadastros_solicitantes(request):
    org = organizacao_do(request.user)
    solicitantes = Solicitante.objects.filter(organizacao=org)
    return render(request, 'agendamento/gestor_cadastros.html', {
        'solicitantes': solicitantes,
    })


@login_required
@exige_gestor
@require_POST
def decidir_cadastro(request, pk):
    org = organizacao_do(request.user)
    solicitante = get_object_or_404(Solicitante, pk=pk, organizacao=org)
    acao = request.POST.get('acao')
    if acao == 'aprovar':
        solicitante.status = Solicitante.STATUS_ATIVO
        msg = f'Cadastro de {solicitante.nome} aprovado.'
    elif acao == 'inativar':
        solicitante.status = Solicitante.STATUS_INATIVO
        msg = f'Cadastro de {solicitante.nome} inativado.'
    else:
        messages.error(request, 'Ação inválida.')
        return redirect('cadastros_solicitantes')
    solicitante.save(update_fields=['status'])
    messages.success(request, msg)
    return redirect('cadastros_solicitantes')


MESES_PT = ['', 'Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho',
            'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro']


@login_required
@exige_gestor
def agenda(request):
    """Calendario mensal das reservas da organizacao."""
    org = organizacao_do(request.user)
    hoje = timezone.localdate()
    try:
        ano = int(request.GET.get('ano', hoje.year))
        mes = int(request.GET.get('mes', hoje.month))
        primeiro = date(ano, mes, 1)
    except (TypeError, ValueError):
        ano, mes = hoje.year, hoje.month
        primeiro = date(ano, mes, 1)

    ultimo = date(ano, mes, _calendar.monthrange(ano, mes)[1])
    reservas = (SolicitacaoVeiculo.objects
                .filter(organizacao=org,
                        status__in=('pendente', 'aprovada', 'em_uso'),
                        saida_prevista__date__lte=ultimo,
                        retorno_previsto__date__gte=primeiro)
                .select_related('veiculo', 'solicitante')
                .order_by('saida_prevista'))

    por_dia = {}
    for s in reservas:
        d0 = max(s.saida_prevista.date(), primeiro)
        d1 = min(s.retorno_previsto.date(), ultimo)
        dia = d0
        while dia <= d1:
            por_dia.setdefault(dia, []).append(s)
            dia += timedelta(days=1)

    cal = _calendar.Calendar(firstweekday=6)  # domingo
    semanas = []
    for semana in cal.monthdatescalendar(ano, mes):
        semanas.append([{
            'data': d,
            'no_mes': d.month == mes,
            'hoje': d == hoje,
            'itens': por_dia.get(d, []),
        } for d in semana])

    mes_ant = (primeiro - timedelta(days=1))
    mes_prox = (ultimo + timedelta(days=1))
    return render(request, 'agendamento/agenda.html', {
        'ano': ano, 'mes': mes, 'mes_nome': MESES_PT[mes],
        'semanas': semanas,
        'dias_semana': ['Dom', 'Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb'],
        'mes_ant': mes_ant, 'mes_prox': mes_prox,
        'total_reservas': reservas.count(),
    })


@login_required
@exige_gestor
def detalhes_solicitante(request, pk):
    org = organizacao_do(request.user)
    solicitante = get_object_or_404(Solicitante, pk=pk, organizacao=org)
    solicitacoes = solicitante.solicitacoes.select_related(
        'veiculo', 'motorista').all()
    return render(request, 'agendamento/gestor_solicitante.html', {
        'solicitante': solicitante,
        'solicitacoes': solicitacoes,
    })
