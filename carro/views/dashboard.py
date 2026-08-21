import calendar
from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.db.models import Max, Sum
from django.db.models.functions import TruncMonth
from django.shortcuts import render
from django.utils import timezone

from carro.models import Custo, PlanoManutencao, Veiculo
from contas.utils import organizacao_do

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
    inicio_mes = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    custos_mes = Custo.objects.filter(veiculo__organizacao=org, data__gte=inicio_mes)
    custo_mes_total = custos_mes.aggregate(t=Sum('valor'))['t'] or 0

    por_categoria = []
    total_cat = float(custo_mes_total) or 1
    for row in custos_mes.values('tipo').annotate(total=Sum('valor')).order_by('-total'):
        valor = float(row['total'] or 0)
        por_categoria.append({
            'rotulo': ROTULOS_TIPO.get(row['tipo'], row['tipo']),
            'total': valor,
            'pct': round(valor / total_cat * 100),
        })

    ranking = list(
        Veiculo.objects.filter(organizacao=org)
        .annotate(total=Sum('custos__valor'))
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
        'custo_mes_total': custo_mes_total,
        'projecao_fechamento': _projecao_fechamento(custo_mes_total),
        'custos_meses': _custos_ultimos_meses(org, 6),
        'por_categoria': por_categoria,
        'ranking': ranking,
        'alertas': alertas,
    }
    return render(request, 'dashboard.html', context)
