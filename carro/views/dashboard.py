from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.db.models import Max, Sum
from django.db.models.functions import TruncMonth
from django.shortcuts import render
from django.utils import timezone

from carro.models import Custo, PlanoManutencao, Veiculo

MESES_PT = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun',
            'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez']


def _km_por_veiculo():
    kms = {}
    veiculos = Veiculo.objects.annotate(
        kmax_ab=Max('abastecimentos__quilometragem'),
        kmax_reg=Max('registros_km__quilometragem'),
    )
    for v in veiculos:
        leituras = [x for x in (v.kmax_ab, v.kmax_reg) if x is not None]
        kms[v.id] = max(leituras) if leituras else None
    return kms


def _custos_ultimos_meses(qtd=6):
    hoje = timezone.now().date()
    inicio = (hoje.replace(day=1) - timedelta(days=30 * (qtd - 1))).replace(day=1)

    por_mes = (
        Custo.objects.filter(data__gte=inicio)
        .annotate(mes=TruncMonth('data'))
        .values('mes')
        .annotate(total=Sum('valor'))
    )
    totais = {c['mes'].strftime('%Y-%m'): float(c['total'] or 0) for c in por_mes}

    # Monta a serie completa dos ultimos `qtd` meses (inclusive os zerados)
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


@login_required
def dashboard(request):
    inicio_mes = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    custo_mes_total = Custo.objects.filter(data__gte=inicio_mes).aggregate(
        t=Sum('valor'))['t'] or 0

    ranking = list(
        Veiculo.objects.annotate(total=Sum('custos__valor'))
        .filter(total__isnull=False)
        .order_by('-total')[:5]
    )

    kms = _km_por_veiculo()
    alertas = []
    for plano in PlanoManutencao.objects.select_related('veiculo'):
        st = plano.status(kms.get(plano.veiculo_id))
        if st['cor'] in ('red', 'yellow'):
            alertas.append({'plano': plano, 'status': st})
    alertas.sort(key=lambda a: 0 if a['status']['cor'] == 'red' else 1)

    context = {
        'total_veiculos': Veiculo.objects.count(),
        'ativos': Veiculo.objects.filter(status='ativo').count(),
        'em_manutencao': Veiculo.objects.filter(status='manutencao').count(),
        'custo_mes_total': custo_mes_total,
        'custos_meses': _custos_ultimos_meses(6),
        'ranking': ranking,
        'alertas': alertas,
    }
    return render(request, 'dashboard.html', context)
