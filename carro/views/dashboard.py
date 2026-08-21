import calendar
from datetime import date, timedelta

from django.contrib.auth.decorators import login_required
from django.db.models import Max, Q, Sum
from django.db.models.functions import TruncMonth
from django.shortcuts import render
from django.utils import timezone

from carro.models import Custo, Documento, PlanoManutencao, Veiculo
from contas.utils import organizacao_do


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


def _agenda_90_dias(org):
    """Reune documentos e manutencoes programadas (por data) que vencem nos
    proximos 90 dias (ou ja vencidos), ordenados por data."""
    hoje = timezone.now().date()
    limite = hoje + timedelta(days=90)
    itens = []

    for doc in Documento.objects.filter(
            veiculo__organizacao=org, vencimento__lte=limite).select_related('veiculo'):
        st = doc.status()
        itens.append({
            'veiculo': doc.veiculo, 'veiculo_id': doc.veiculo_id,
            'titulo': doc.get_tipo_display(), 'categoria': 'Documento',
            'data': doc.vencimento, 'dias': st['dias'], 'cor': st['cor'],
        })

    for plano in PlanoManutencao.objects.filter(
            veiculo__organizacao=org,
            intervalo_dias__isnull=False,
            data_referencia__isnull=False).select_related('veiculo'):
        prox = plano.proxima_data
        if not prox or prox > limite:
            continue
        dias = (prox - hoje).days
        cor = 'red' if dias <= 0 else 'yellow' if dias <= 15 else 'green'
        itens.append({
            'veiculo': plano.veiculo, 'veiculo_id': plano.veiculo_id,
            'titulo': plano.descricao, 'categoria': 'Manutenção',
            'data': prox, 'dias': dias, 'cor': cor,
        })

    itens.sort(key=lambda i: i['data'])
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
            'rotulo': ROTULOS_TIPO.get(row['tipo'], row['tipo']),
            'total': valor,
            'pct': round(valor / total_cat * 100),
        })

    ranking = list(
        Veiculo.objects.filter(organizacao=org)
        .annotate(total=Sum('custos__valor', filter=filtro_ranking))
        .filter(total__isnull=False)
        .order_by('-total')[:5]
    )

    kms = _km_por_veiculo(org)
    alertas = []
    for plano in PlanoManutencao.objects.filter(
            veiculo__organizacao=org).select_related('veiculo'):
        st = plano.status(kms.get(plano.veiculo_id))
        if st['cor'] in ('red', 'yellow'):
            alertas.append({'plano': plano, 'status': st})
    alertas.sort(key=lambda a: 0 if a['status']['cor'] == 'red' else 1)

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
        'ranking': ranking,
        'alertas': alertas,
        'agenda_90': _agenda_90_dias(org),
    }
    return render(request, 'dashboard.html', context)
