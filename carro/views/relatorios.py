import csv

from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.http import HttpResponse
from django.shortcuts import render

from carro.models import Custo


def _custos_filtrados(request):
    from contas.utils import organizacao_do
    custos = Custo.objects.select_related('veiculo').filter(
        veiculo__organizacao=organizacao_do(request.user))
    inicio = request.GET.get('inicio')
    fim = request.GET.get('fim')
    if inicio:
        custos = custos.filter(data__gte=inicio)
    if fim:
        custos = custos.filter(data__lte=fim)
    return custos, inicio, fim


@login_required
def relatorios(request):
    custos, inicio, fim = _custos_filtrados(request)

    por_categoria = list(
        custos.values('tipo').annotate(total=Sum('valor')).order_by('-total')
    )
    total_geral = custos.aggregate(t=Sum('valor'))['t'] or 0

    rotulos = dict(Custo.TIPO_CHOICES)
    for item in por_categoria:
        item['rotulo'] = rotulos.get(item['tipo'], item['tipo'])
        item['pct'] = round(float(item['total']) / float(total_geral) * 100) if total_geral else 0

    por_veiculo = list(
        custos.values('veiculo__marca', 'veiculo__modelo')
        .annotate(total=Sum('valor')).order_by('-total')
    )

    context = {
        'por_categoria': por_categoria,
        'por_veiculo': por_veiculo,
        'total_geral': total_geral,
        'inicio': inicio or '',
        'fim': fim or '',
    }
    return render(request, 'relatorios.html', context)


@login_required
def exportar_custos(request):
    custos, _, _ = _custos_filtrados(request)
    custos = custos.order_by('data')
    formato = request.GET.get('formato', 'csv')
    cabecalho = ['Data', 'Veículo', 'Tipo', 'Descrição', 'Valor']
    rotulos = dict(Custo.TIPO_CHOICES)

    if formato == 'xlsx':
        from openpyxl import Workbook

        wb = Workbook()
        ws = wb.active
        ws.title = 'Custos'
        ws.append(cabecalho)
        for c in custos:
            ws.append([
                c.data.strftime('%d/%m/%Y'),
                f'{c.veiculo.marca} {c.veiculo.modelo}',
                rotulos.get(c.tipo, c.tipo),
                c.descricao,
                float(c.valor),
            ])
        resposta = HttpResponse(
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        resposta['Content-Disposition'] = 'attachment; filename="custos.xlsx"'
        wb.save(resposta)
        return resposta

    # CSV (padrao)
    resposta = HttpResponse(content_type='text/csv; charset=utf-8')
    resposta['Content-Disposition'] = 'attachment; filename="custos.csv"'
    resposta.write('﻿')  # BOM para acentuacao no Excel
    escritor = csv.writer(resposta, delimiter=';')
    escritor.writerow(cabecalho)
    for c in custos:
        escritor.writerow([
            c.data.strftime('%d/%m/%Y'),
            f'{c.veiculo.marca} {c.veiculo.modelo}',
            rotulos.get(c.tipo, c.tipo),
            c.descricao,
            f'{c.valor:.2f}'.replace('.', ','),
        ])
    return resposta
