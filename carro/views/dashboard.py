from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.db.models import Max
from django.shortcuts import render
from django.utils import timezone

from carro.models import (
    Documento,
    EscalaDiaria,
    PlanoManutencao,
    SolicitacaoVeiculo,
    Veiculo,
)
from contas.utils import exige_gestor, organizacao_do

PERIODOS_AGENDA = [7, 15, 30, 45, 60, 90]
PERIODOS_HOJE = [1, 7, 15, 30]


def _km_por_veiculo(org):
    kms = {}
    veiculos = Veiculo.objects.filter(organizacao=org).annotate(
        kmax_ab=Max('abastecimentos__quilometragem'),
        kmax_reg=Max('registros_km__quilometragem'),
    )
    for v in veiculos:
        leituras = [x for x in (v.kmax_ab, v.kmax_reg) if x is not None]
        kms[v.id] = max(leituras) if leituras else None
    return kms


def _agenda(org, kms, dias):
    """Agenda vertical: documentos e manutencoes a vencer, alertas por km, e a
    escala futura, dentro da janela de `dias`. Eventos criticos (vencidos /
    atrasados) ficam fixos ate 90 dias, mesmo com janela menor."""
    hoje = timezone.now().date()
    fim = hoje + timedelta(days=dias)
    fim_critico = hoje + timedelta(days=90)
    itens = []

    for doc in Documento.objects.filter(
            veiculo__organizacao=org, vencimento__lte=fim_critico
            ).select_related('veiculo'):
        st = doc.status()
        critico = st['cor'] == 'red'
        if doc.vencimento <= fim or critico:
            itens.append({
                'veiculo': doc.veiculo, 'veiculo_id': doc.veiculo_id,
                'titulo': doc.get_tipo_display(), 'categoria': 'Documento',
                'data': doc.vencimento, 'dias': st['dias'], 'cor': st['cor'],
                'detalhe': st['detalhe'], 'critico': critico})

    for plano in PlanoManutencao.objects.filter(
            veiculo__organizacao=org).select_related('veiculo'):
        st = plano.status(kms.get(plano.veiculo_id))
        critico = st['cor'] == 'red'
        prox = plano.proxima_data
        tem_data = prox is not None and prox <= fim_critico
        if tem_data and (prox <= fim or critico):
            data, dias_i = prox, (prox - hoje).days
        elif not tem_data and st['cor'] in ('red', 'yellow'):
            data, dias_i = None, None
        else:
            continue
        itens.append({
            'veiculo': plano.veiculo, 'veiculo_id': plano.veiculo_id,
            'titulo': plano.descricao, 'categoria': 'Manutenção',
            'data': data, 'dias': dias_i, 'cor': st['cor'],
            'detalhe': st['detalhe'], 'critico': critico})

    for e in EscalaDiaria.objects.filter(
            organizacao=org, data__gt=hoje, data__lte=fim
            ).select_related('veiculo', 'motorista'):
        itens.append({
            'veiculo': e.veiculo, 'veiculo_id': e.veiculo_id,
            'titulo': e.motorista.nome, 'categoria': 'Escala',
            'data': e.data, 'dias': (e.data - hoje).days, 'cor': 'escala',
            'detalhe': 'Escalado', 'critico': False})

    ordem_cor = {'red': 0, 'yellow': 1, 'green': 2, 'escala': 3, 'gray': 4}
    itens.sort(key=lambda i: (
        0 if i['critico'] else 1,
        0 if i['data'] else 1,
        i['data'].toordinal() if i['data'] else 0,
        ordem_cor.get(i['cor'], 9),
    ))
    return itens


@login_required
@exige_gestor
def dashboard(request):
    """Painel operacional: frota, reservas/escala do dia e agenda de pendências.
    A parte financeira fica no módulo Financeiro."""
    org = organizacao_do(request.user)

    try:
        agenda_dias = int(request.GET.get('agenda_dias', 30))
    except (TypeError, ValueError):
        agenda_dias = 30
    if agenda_dias not in PERIODOS_AGENDA:
        agenda_dias = 30

    # Janela dos cards de reservas/escala (padrao hoje; max 30 dias).
    try:
        hoje_dias = int(request.GET.get('hoje_dias', 1))
    except (TypeError, ValueError):
        hoje_dias = 1
    if hoje_dias not in PERIODOS_HOJE:
        hoje_dias = 1

    hoje = timezone.now().date()
    fim_hoje = hoje + timedelta(days=hoje_dias - 1)
    reservas_hoje = (SolicitacaoVeiculo.objects
                     .filter(organizacao=org, status__in=('aprovada', 'em_uso'),
                             saida_prevista__date__lte=fim_hoje,
                             retorno_previsto__date__gte=hoje)
                     .select_related('veiculo', 'solicitante', 'motorista')
                     .order_by('saida_prevista'))
    escala_hoje = (EscalaDiaria.objects
                   .filter(organizacao=org, data__gte=hoje, data__lte=fim_hoje)
                   .select_related('veiculo', 'motorista')
                   .order_by('data', 'veiculo__marca', 'veiculo__modelo'))

    context = {
        'total_veiculos': Veiculo.objects.filter(organizacao=org).count(),
        'ativos': Veiculo.objects.filter(organizacao=org, status='ativo').count(),
        'em_manutencao': Veiculo.objects.filter(
            organizacao=org, status='manutencao').count(),
        'agenda': _agenda(org, _km_por_veiculo(org), agenda_dias),
        'agenda_dias': agenda_dias,
        'periodos_agenda': PERIODOS_AGENDA,
        'reservas_hoje': reservas_hoje,
        'escala_hoje': escala_hoje,
        'hoje_dias': hoje_dias,
        'periodos_hoje': PERIODOS_HOJE,
    }
    return render(request, 'dashboard.html', context)
