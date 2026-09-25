import calendar
from datetime import date, timedelta

from django.contrib.auth.decorators import login_required
from django.db.models import Max, Q, Sum
from django.db.models.functions import TruncMonth
from django.shortcuts import render
from django.utils import timezone

from carro.models import (
    Custo,
    Documento,
    EscalaDiaria,
    PlanoManutencao,
    SolicitacaoVeiculo,
    Veiculo,
)
from contas.utils import exige_gestor, organizacao_do

PERIODOS_AGENDA = [7, 15, 30, 45, 60, 90]


MESES_LONGOS_PT = ['janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho',
                   'julho', 'agosto', 'setembro', 'outubro', 'novembro', 'dezembro']


def _periodo_do_request(request):
    """Resolve o periodo do dashboard a partir dos parametros GET.

    Retorna (inicio, fim, rotulo, preset, eh_mes_atual). `fim` pode ser None
    (ate hoje). `eh_mes_atual` habilita a projecao de fechamento.
    """
    hoje = timezone.now().date()
    preset = request.GET.get('periodo', 'mes_atual')

    if preset == 'mes_anterior':
        primeiro_atual = hoje.replace(day=1)
        fim = primeiro_atual - timedelta(days=1)
        inicio = fim.replace(day=1)
        rotulo = f'{MESES_LONGOS_PT[inicio.month - 1].capitalize()}/{inicio.year}'
        return inicio, fim, rotulo, preset, False

    if preset == '3meses':
        mes = hoje.month - 2
        ano = hoje.year
        if mes <= 0:
            mes += 12
            ano -= 1
        inicio = date(ano, mes, 1)
        return inicio, None, 'Últimos 3 meses', preset, False

    if preset == 'ano':
        inicio = date(hoje.year, 1, 1)
        return inicio, None, f'Ano de {hoje.year}', preset, False

    if preset == 'custom':
        inicio_str = request.GET.get('inicio')
        fim_str = request.GET.get('fim')
        inicio = date.fromisoformat(inicio_str) if inicio_str else hoje.replace(day=1)
        fim = date.fromisoformat(fim_str) if fim_str else None
        partes = [inicio.strftime('%d/%m/%Y'), fim.strftime('%d/%m/%Y') if fim else 'hoje']
        return inicio, fim, ' — '.join(partes), preset, False

    # mes_atual (padrao)
    inicio = hoje.replace(day=1)
    rotulo = f'{MESES_LONGOS_PT[inicio.month - 1].capitalize()}/{inicio.year}'
    return inicio, None, rotulo, 'mes_atual', True


def _patrimonio(org):
    """Soma o valor de aquisicao e o valor estimado atual da frota."""
    aquisicao = atual = 0.0
    for v in Veiculo.objects.filter(organizacao=org).exclude(
            valor_aquisicao__isnull=True):
        est = v.valor_estimado_atual()
        if est:
            aquisicao += est['aquisicao']
            atual += est['atual']
    if aquisicao <= 0:
        return None
    return {
        'aquisicao': aquisicao,
        'atual': atual,
        'depreciacao': aquisicao - atual,
        'pct': round((aquisicao - atual) / aquisicao * 100),
    }


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
            # Alerta so por quilometragem (sem data prevista).
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

ROTULOS_TIPO = dict(Custo.TIPO_CHOICES)
MESES_PT = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun',
            'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez']


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


def _custos_ultimos_meses(org, qtd=6):
    hoje = timezone.now().date()
    inicio = (hoje.replace(day=1) - timedelta(days=30 * (qtd - 1))).replace(day=1)

    por_mes = (
        Custo.objects.filter(veiculo__organizacao=org, data__gte=inicio)
        .annotate(mes=TruncMonth('data'))
        .values('mes')
        .annotate(total=Sum('valor'))
    )
    totais = {c['mes'].strftime('%Y-%m'): float(c['total'] or 0) for c in por_mes}

    serie = []
    ano, mes = inicio.year, inicio.month
    for _ in range(qtd):
        chave = f'{ano:04d}-{mes:02d}'
        serie.append({'label': f'{MESES_PT[mes - 1]}/{str(ano)[2:]}',
                      'total': totais.get(chave, 0.0)})
        mes += 1
        if mes > 12:
            mes = 1
            ano += 1

    maximo = max((s['total'] for s in serie), default=0) or 1
    for s in serie:
        s['pct'] = round(s['total'] / maximo * 100)
    return serie


def _projecao_fechamento(custo_ate_agora):
    """Projeta o custo de fechamento do mes pelo ritmo atual (regra de tres
    entre dias decorridos e dias do mes)."""
    hoje = timezone.now().date()
    dias_no_mes = calendar.monthrange(hoje.year, hoje.month)[1]
    dias_decorridos = hoje.day
    if dias_decorridos <= 0:
        return float(custo_ate_agora)
    return float(custo_ate_agora) / dias_decorridos * dias_no_mes


@login_required
@exige_gestor
def dashboard(request):
    org = organizacao_do(request.user)
    inicio, fim, periodo_rotulo, periodo_preset, eh_mes_atual = _periodo_do_request(request)

    filtro_periodo = Q(data__gte=inicio)
    filtro_ranking = Q(custos__data__gte=inicio)
    if fim:
        filtro_periodo &= Q(data__lte=fim)
        filtro_ranking &= Q(custos__data__lte=fim)
    custos_periodo = Custo.objects.filter(veiculo__organizacao=org).filter(filtro_periodo)
    custo_periodo_total = custos_periodo.aggregate(t=Sum('valor'))['t'] or 0

    por_categoria = []
    total_cat = float(custo_periodo_total) or 1
    for row in custos_periodo.values('tipo').annotate(total=Sum('valor')).order_by('-total'):
        valor = float(row['total'] or 0)
        por_categoria.append({
            'tipo': row['tipo'],
            'rotulo': ROTULOS_TIPO.get(row['tipo'], row['tipo']),
            'total': valor,
            'pct': round(valor / total_cat * 100),
        })

    custo_documentacao = float(
        custos_periodo.filter(tipo__in=Custo.CATEGORIAS_DOCUMENTO)
        .aggregate(t=Sum('valor'))['t'] or 0)

    ranking = list(
        Veiculo.objects.filter(organizacao=org)
        .annotate(total=Sum('custos__valor', filter=filtro_ranking))
        .filter(total__isnull=False)
        .order_by('-total')[:5]
    )

    kms = _km_por_veiculo(org)

    # Janela da agenda (padrao 30 dias).
    try:
        agenda_dias = int(request.GET.get('agenda_dias', 30))
    except (TypeError, ValueError):
        agenda_dias = 30
    if agenda_dias not in PERIODOS_AGENDA:
        agenda_dias = 30

    hoje = timezone.now().date()
    reservas_hoje = (SolicitacaoVeiculo.objects
                     .filter(organizacao=org, status__in=('aprovada', 'em_uso'),
                             saida_prevista__date__lte=hoje,
                             retorno_previsto__date__gte=hoje)
                     .select_related('veiculo', 'solicitante', 'motorista')
                     .order_by('saida_prevista'))
    escala_hoje = (EscalaDiaria.objects
                   .filter(organizacao=org, data=hoje)
                   .select_related('veiculo', 'motorista')
                   .order_by('veiculo__marca', 'veiculo__modelo'))

    context = {
        'total_veiculos': Veiculo.objects.filter(organizacao=org).count(),
        'ativos': Veiculo.objects.filter(organizacao=org, status='ativo').count(),
        'em_manutencao': Veiculo.objects.filter(organizacao=org, status='manutencao').count(),
        'custo_mes_total': custo_periodo_total,
        'projecao_fechamento': _projecao_fechamento(custo_periodo_total),
        'mostrar_projecao': eh_mes_atual,
        'periodo_rotulo': periodo_rotulo,
        'periodo_preset': periodo_preset,
        'periodo_inicio': inicio.isoformat(),
        'periodo_fim': fim.isoformat() if fim else '',
        'patrimonio': _patrimonio(org),
        'custos_meses': _custos_ultimos_meses(org, 6),
        'por_categoria': por_categoria,
        'custo_documentacao': custo_documentacao,
        'ano_corrente': timezone.now().year,
        'ranking': ranking,
        'agenda': _agenda(org, kms, agenda_dias),
        'agenda_dias': agenda_dias,
        'periodos_agenda': PERIODOS_AGENDA,
        'reservas_hoje': reservas_hoje,
        'escala_hoje': escala_hoje,
    }
    return render(request, 'dashboard.html', context)
