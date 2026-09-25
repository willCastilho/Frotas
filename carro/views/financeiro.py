"""Modulo Financeiro: tudo relacionado aos gastos com os veiculos.

Concentra a analise de custos que antes ficava no Dashboard: visao geral
(KPIs + evolucao), por categoria, por veiculo, combustivel/consumo,
documentacao e patrimonio/depreciacao. O detalhamento e as exportacoes ficam
na pagina de Relatorios (linkada a partir daqui).
"""
import calendar
from datetime import date, timedelta

from django.contrib.auth.decorators import login_required
from django.db.models import Q, Sum
from django.db.models.functions import TruncMonth
from django.shortcuts import render
from django.utils import timezone

from carro.models import Abastecimento, Custo, Veiculo
from contas.utils import exige_gestor, organizacao_do

MESES_LONGOS_PT = ['janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho',
                   'julho', 'agosto', 'setembro', 'outubro', 'novembro', 'dezembro']
MESES_PT = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun',
            'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez']
ROTULOS_TIPO = dict(Custo.TIPO_CHOICES)


def periodo_do_request(request):
    """Resolve o periodo a partir dos parametros GET. Retorna
    (inicio, fim, rotulo, preset, eh_mes_atual). `fim` None = ate hoje."""
    hoje = timezone.now().date()
    preset = request.GET.get('periodo', 'mes_atual')

    if preset == 'mes_anterior':
        primeiro_atual = hoje.replace(day=1)
        fim = primeiro_atual - timedelta(days=1)
        inicio = fim.replace(day=1)
        rotulo = f'{MESES_LONGOS_PT[inicio.month - 1].capitalize()}/{inicio.year}'
        return inicio, fim, rotulo, preset, False
    if preset == '3meses':
        mes, ano = hoje.month - 2, hoje.year
        if mes <= 0:
            mes += 12
            ano -= 1
        return date(ano, mes, 1), None, 'Últimos 3 meses', preset, False
    if preset == 'ano':
        return date(hoje.year, 1, 1), None, f'Ano de {hoje.year}', preset, False
    if preset == 'custom':
        inicio_str = request.GET.get('inicio')
        fim_str = request.GET.get('fim')
        inicio = date.fromisoformat(inicio_str) if inicio_str else hoje.replace(day=1)
        fim = date.fromisoformat(fim_str) if fim_str else None
        partes = [inicio.strftime('%d/%m/%Y'), fim.strftime('%d/%m/%Y') if fim else 'hoje']
        return inicio, fim, ' — '.join(partes), preset, False

    inicio = hoje.replace(day=1)
    rotulo = f'{MESES_LONGOS_PT[inicio.month - 1].capitalize()}/{inicio.year}'
    return inicio, None, rotulo, 'mes_atual', True


def _patrimonio(org):
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
        'aquisicao': aquisicao, 'atual': atual,
        'depreciacao': aquisicao - atual,
        'pct': round((aquisicao - atual) / aquisicao * 100),
    }


def _custos_ultimos_meses(org, qtd=6):
    hoje = timezone.now().date()
    inicio = (hoje.replace(day=1) - timedelta(days=30 * (qtd - 1))).replace(day=1)
    por_mes = (Custo.objects.filter(veiculo__organizacao=org, data__gte=inicio)
               .annotate(mes=TruncMonth('data')).values('mes')
               .annotate(total=Sum('valor')))
    totais = {c['mes'].strftime('%Y-%m'): float(c['total'] or 0) for c in por_mes}
    serie = []
    ano, mes = inicio.year, inicio.month
    for _ in range(qtd):
        serie.append({'label': f'{MESES_PT[mes - 1]}/{str(ano)[2:]}',
                      'total': totais.get(f'{ano:04d}-{mes:02d}', 0.0)})
        mes += 1
        if mes > 12:
            mes, ano = 1, ano + 1
    maximo = max((s['total'] for s in serie), default=0) or 1
    for s in serie:
        s['pct'] = round(s['total'] / maximo * 100)
    return serie


def _projecao_fechamento(custo_ate_agora):
    hoje = timezone.now().date()
    dias_no_mes = calendar.monthrange(hoje.year, hoje.month)[1]
    if hoje.day <= 0:
        return float(custo_ate_agora)
    return float(custo_ate_agora) / hoje.day * dias_no_mes


@login_required
@exige_gestor
def financeiro(request):
    org = organizacao_do(request.user)
    inicio, fim, periodo_rotulo, periodo_preset, eh_mes_atual = periodo_do_request(request)
    ano_corrente = timezone.now().year

    filtro = Q(data__gte=inicio)
    filtro_rank = Q(custos__data__gte=inicio)
    filtro_ab = Q(data__gte=inicio)
    if fim:
        filtro &= Q(data__lte=fim)
        filtro_rank &= Q(custos__data__lte=fim)
        filtro_ab &= Q(data__lte=fim)

    custos_periodo = Custo.objects.filter(veiculo__organizacao=org).filter(filtro)
    total = custos_periodo.aggregate(t=Sum('valor'))['t'] or 0

    # Por categoria
    por_categoria = []
    base = float(total) or 1
    for row in custos_periodo.values('tipo').annotate(t=Sum('valor')).order_by('-t'):
        v = float(row['t'] or 0)
        por_categoria.append({
            'tipo': row['tipo'], 'rotulo': ROTULOS_TIPO.get(row['tipo'], row['tipo']),
            'total': v, 'pct': round(v / base * 100)})

    custo_documentacao = float(
        custos_periodo.filter(tipo__in=Custo.CATEGORIAS_DOCUMENTO)
        .aggregate(t=Sum('valor'))['t'] or 0)
    custo_combustivel = float(
        custos_periodo.filter(tipo='combustivel')
        .aggregate(t=Sum('valor'))['t'] or 0)
    custo_manutencao = float(
        custos_periodo.filter(tipo='manutencao')
        .aggregate(t=Sum('valor'))['t'] or 0)

    # Combustivel / consumo
    abast = Abastecimento.objects.filter(
        veiculo__organizacao=org).filter(filtro_ab)
    litros = float(abast.aggregate(t=Sum('litros'))['t'] or 0)
    preco_medio_litro = (custo_combustivel / litros) if litros else 0

    # Por veiculo (vida inteira): total, custo/km e consumo
    veiculos = list(
        Veiculo.objects.filter(organizacao=org)
        .annotate(total_vida=Sum('custos__valor'))
        .order_by('marca', 'modelo'))
    por_veiculo = []
    for v in veiculos:
        por_veiculo.append({
            'obj': v,
            'total_vida': float(v.total_vida or 0),
            'custo_km': v.custo_por_km(),
            'consumo': v.consumo_medio(),
        })

    # Ranking do periodo (top 5)
    ranking = list(
        Veiculo.objects.filter(organizacao=org)
        .annotate(total=Sum('custos__valor', filter=filtro_rank))
        .filter(total__isnull=False).order_by('-total')[:5])

    context = {
        'periodo_rotulo': periodo_rotulo,
        'periodo_preset': periodo_preset,
        'periodo_inicio': inicio.isoformat(),
        'periodo_fim': fim.isoformat() if fim else '',
        'ano_corrente': ano_corrente,
        'total': total,
        'projecao': _projecao_fechamento(total),
        'mostrar_projecao': eh_mes_atual,
        'por_categoria': por_categoria,
        'custo_documentacao': custo_documentacao,
        'custo_combustivel': custo_combustivel,
        'custo_manutencao': custo_manutencao,
        'litros': litros,
        'preco_medio_litro': preco_medio_litro,
        'custos_meses': _custos_ultimos_meses(org, 6),
        'por_veiculo': por_veiculo,
        'ranking': ranking,
        'patrimonio': _patrimonio(org),
    }
    return render(request, 'financeiro.html', context)
