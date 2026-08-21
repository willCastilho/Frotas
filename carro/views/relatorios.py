import csv

from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone

from carro.models import Custo


def _exportar_pdf(custos, inicio, fim, rotulos):
    """Gera um PDF com a lista de custos do periodo e o total geral."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import (SimpleDocTemplate, Table, TableStyle,
                                    Paragraph, Spacer)

    resposta = HttpResponse(content_type='application/pdf')
    resposta['Content-Disposition'] = 'attachment; filename="relatorio-custos.pdf"'

    doc = SimpleDocTemplate(resposta, pagesize=A4,
                            topMargin=1.5 * cm, bottomMargin=1.5 * cm,
                            leftMargin=1.5 * cm, rightMargin=1.5 * cm)
    estilos = getSampleStyleSheet()
    elementos = [Paragraph('Relatório de Custos', estilos['Title'])]

    periodo = 'Período: '
    periodo += f'de {inicio} ' if inicio else 'desde o início '
    periodo += f'até {fim}' if fim else 'até hoje'
    elementos.append(Paragraph(periodo, estilos['Normal']))
    elementos.append(Paragraph(
        'Emitido em ' + timezone.now().strftime('%d/%m/%Y %H:%M'),
        estilos['Normal']))
    elementos.append(Spacer(1, 0.6 * cm))

    dados = [['Data', 'Veículo', 'Tipo', 'Descrição', 'Valor (R$)']]
    total = 0
    for c in custos:
        total += float(c.valor)
        descricao = (c.descricao or '')[:40]
        dados.append([
            c.data.strftime('%d/%m/%Y'),
            f'{c.veiculo.marca} {c.veiculo.modelo}',
            rotulos.get(c.tipo, c.tipo),
            descricao,
            f'{c.valor:.2f}'.replace('.', ','),
        ])
    dados.append(['', '', '', 'TOTAL', f'{total:.2f}'.replace('.', ',')])

    tabela = Table(dados, colWidths=[2.3 * cm, 4.5 * cm, 3 * cm, 5 * cm, 2.5 * cm],
                   repeatRows=1)
    tabela.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1f2937')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('ALIGN', (4, 0), (4, -1), 'RIGHT'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, colors.HexColor('#f3f4f6')]),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#e5e7eb')),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#d1d5db')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    elementos.append(tabela)
    doc.build(elementos)
    return resposta


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
    custos, inicio, fim = _custos_filtrados(request)
    custos = custos.order_by('data')
    formato = request.GET.get('formato', 'csv')
    cabecalho = ['Data', 'Veículo', 'Tipo', 'Descrição', 'Valor']
    rotulos = dict(Custo.TIPO_CHOICES)

    if formato == 'pdf':
        return _exportar_pdf(custos, inicio, fim, rotulos)

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
