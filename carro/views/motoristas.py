from datetime import date, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from carro.forms import EscalaMontarForm, MotoristaForm
from carro.models import EscalaDiaria, Motorista, Veiculo
from contas.utils import exige_escrita, exige_gestor, organizacao_do


def _motoristas_da_org(request):
    return Motorista.objects.filter(organizacao=organizacao_do(request.user))


@login_required
@exige_gestor
def motoristas(request):
    busca = request.GET.get('busca', '').strip()
    lista = _motoristas_da_org(request)
    if busca:
        lista = lista.filter(Q(nome__icontains=busca) | Q(cnh__icontains=busca))
    motoristas_info = [
        {'obj': m, 'veiculo': m.veiculo_atual(), 'cnh': m.cnh_status()}
        for m in lista
    ]
    return render(request, 'motoristas/lista.html',
                  {'motoristas': motoristas_info, 'busca': busca})


@login_required
@exige_gestor
def detalhes_escala(request, pk):
    org = organizacao_do(request.user)
    escala = get_object_or_404(
        EscalaDiaria.objects.select_related(
            'veiculo', 'motorista', 'criado_por'),
        pk=pk, organizacao=org)
    return render(request, 'motoristas/escala_detalhe.html', {'e': escala})


@login_required
@exige_gestor
def detalhes_motorista(request, motorista_id):
    motorista = get_object_or_404(_motoristas_da_org(request), id=motorista_id)
    historico = motorista.escalas.select_related('veiculo').all()[:60]
    return render(request, 'motoristas/detalhes.html', {
        'motorista': motorista,
        'cnh': motorista.cnh_status(),
        'veiculo_atual': motorista.veiculo_atual(),
        'historico': historico,
    })


@login_required
@exige_escrita
def novo_motorista(request):
    form = MotoristaForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        motorista = form.save(commit=False)
        motorista.organizacao = organizacao_do(request.user)
        motorista.save()
        messages.success(request, 'Motorista cadastrado com sucesso!')
        return redirect('detalhes_motorista', motorista_id=motorista.id)
    return render(request, 'motoristas/form.html',
                  {'form': form, 'titulo': 'Novo Motorista'})


@login_required
@exige_escrita
def editar_motorista(request, motorista_id):
    motorista = get_object_or_404(_motoristas_da_org(request), id=motorista_id)
    form = MotoristaForm(request.POST or None, instance=motorista)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Motorista atualizado com sucesso!')
        return redirect('detalhes_motorista', motorista_id=motorista.id)
    return render(request, 'motoristas/form.html',
                  {'form': form, 'titulo': 'Editar Motorista', 'motorista': motorista})


@login_required
@exige_escrita
@require_POST
def excluir_motorista(request, motorista_id):
    motorista = get_object_or_404(_motoristas_da_org(request), id=motorista_id)
    motorista.delete()
    messages.success(request, 'Motorista excluído.')
    return redirect('motoristas')


def _dia_valido(dia, somente_uteis):
    return not (somente_uteis and dia.weekday() >= 5)  # 5=sab, 6=dom


@login_required
@exige_gestor
def escala(request):
    """Escala de utilizacao do dia + formulario para montar a escala por
    periodo. O gestor define qual veiculo vai para cada motorista no dia."""
    org = organizacao_do(request.user)
    data_str = request.GET.get('data') or timezone.localdate().isoformat()
    try:
        data = date.fromisoformat(data_str)
    except ValueError:
        data = timezone.localdate()

    inicial = {'data_inicio': data.isoformat(), 'data_fim': data.isoformat()}
    veic_id = request.GET.get('veiculo')
    if veic_id:
        inicial['veiculo'] = veic_id
    form = EscalaMontarForm(organizacao=org, initial=inicial)

    escalas = (EscalaDiaria.objects
               .filter(organizacao=org, data=data)
               .select_related('veiculo', 'motorista'))
    com_veiculo = {e.veiculo_id for e in escalas}
    sem_escala = Veiculo.objects.filter(
        organizacao=org, status='ativo').exclude(id__in=com_veiculo)

    return render(request, 'motoristas/escala.html', {
        'data': data,
        'dia_anterior': data - timedelta(days=1),
        'dia_seguinte': data + timedelta(days=1),
        'escalas': escalas,
        'sem_escala': sem_escala,
        'form': form,
    })


@login_required
@exige_escrita
@require_POST
def montar_escala(request):
    """Cria a escala de cada dia do periodo, respeitando as travas: 1 carro por
    motorista/dia e 1 motorista por carro/dia, carro sem documento vencido e
    motorista com CNH em dia."""
    org = organizacao_do(request.user)
    form = EscalaMontarForm(request.POST, organizacao=org)
    if not form.is_valid():
        # Reexibe a tela da escala com os erros.
        data = form.cleaned_data.get('data_inicio') or timezone.localdate()
        escalas = (EscalaDiaria.objects.filter(organizacao=org, data=data)
                   .select_related('veiculo', 'motorista'))
        return render(request, 'motoristas/escala.html', {
            'data': data,
            'dia_anterior': data - timedelta(days=1),
            'dia_seguinte': data + timedelta(days=1),
            'escalas': escalas,
            'sem_escala': Veiculo.objects.filter(
                organizacao=org, status='ativo').exclude(
                id__in={e.veiculo_id for e in escalas}),
            'form': form,
        })

    d = form.cleaned_data
    motorista, veiculo = d['motorista'], d['veiculo']
    inicio, fim, uteis = d['data_inicio'], d['data_fim'], d['somente_dias_uteis']
    obs = d.get('observacao', '')
    destino = d.get('destino', '')

    criados = 0
    conflitos = []
    dia = inicio
    while dia <= fim:
        if not _dia_valido(dia, uteis):
            dia += timedelta(days=1)
            continue
        motivo = None
        if veiculo.documentos.filter(vencimento__lt=dia).exists():
            motivo = 'veículo com documento vencido'
        elif motorista.cnh_validade and motorista.cnh_validade < dia:
            motivo = 'CNH do motorista vencida'
        elif EscalaDiaria.objects.filter(
                organizacao=org, data=dia, veiculo=veiculo).exists():
            motivo = 'veículo já escalado'
        elif EscalaDiaria.objects.filter(
                organizacao=org, data=dia, motorista=motorista).exists():
            motivo = 'motorista já escalado'
        if motivo:
            conflitos.append(f'{dia:%d/%m}: {motivo}')
        else:
            EscalaDiaria.objects.create(
                organizacao=org, data=dia, veiculo=veiculo,
                motorista=motorista, destino=destino, observacao=obs,
                criado_por=request.user)
            criados += 1
        dia += timedelta(days=1)

    if criados:
        messages.success(request, f'{criados} dia(s) escalado(s) para '
                         f'{motorista.nome} no {veiculo}.')
    if conflitos:
        messages.warning(request, 'Dias não escalados — ' + '; '.join(conflitos[:15])
                         + ('…' if len(conflitos) > 15 else ''))
    if not criados and not conflitos:
        messages.info(request, 'Nenhum dia no período selecionado.')
    return redirect(f"{reverse('escala')}?data={inicio.isoformat()}")


@login_required
@exige_escrita
@require_POST
def remover_escala(request, pk):
    esc = get_object_or_404(
        EscalaDiaria, pk=pk, organizacao=organizacao_do(request.user))
    dia = esc.data
    esc.delete()
    messages.success(request, 'Escala removida.')
    return redirect(f"{reverse('escala')}?data={dia.isoformat()}")


@login_required
@exige_gestor
def relatorio_motoristas(request):
    """Mostra qual motorista estava em qual veiculo em uma data (pela escala)."""
    org = organizacao_do(request.user)
    data_str = request.GET.get('data') or timezone.localdate().isoformat()
    try:
        data = date.fromisoformat(data_str)
    except ValueError:
        data = timezone.localdate()

    alocacoes = (EscalaDiaria.objects
                 .filter(organizacao=org, data=data)
                 .select_related('veiculo', 'motorista')
                 .order_by('veiculo__marca', 'veiculo__modelo'))

    if request.GET.get('formato') == 'csv':
        return _exportar_alocacoes_csv(alocacoes, data)

    com_motorista = {a.veiculo_id for a in alocacoes}
    sem_motorista = Veiculo.objects.filter(organizacao=org).exclude(
        id__in=com_motorista)

    return render(request, 'motoristas/relatorio.html', {
        'data': data.isoformat(),
        'alocacoes': alocacoes,
        'sem_motorista': sem_motorista,
    })


def _exportar_alocacoes_csv(alocacoes, data):
    import csv

    from django.http import HttpResponse

    resposta = HttpResponse(content_type='text/csv; charset=utf-8')
    resposta['Content-Disposition'] = (
        f'attachment; filename="motoristas-{data.isoformat()}.csv"')
    resposta.write('﻿')
    escritor = csv.writer(resposta, delimiter=';')
    escritor.writerow(['Data', 'Veículo', 'Placa', 'Motorista', 'CNH',
                       'Observação'])
    for a in alocacoes:
        escritor.writerow([
            data.strftime('%d/%m/%Y'),
            f'{a.veiculo.marca} {a.veiculo.modelo}',
            a.veiculo.placa,
            a.motorista.nome,
            a.motorista.cnh,
            a.observacao,
        ])
    return resposta
