from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from carro.forms import AtribuicaoVeiculoForm, MotoristaForm
from carro.models import AtribuicaoVeiculo, Motorista, Veiculo
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
def detalhes_motorista(request, motorista_id):
    motorista = get_object_or_404(_motoristas_da_org(request), id=motorista_id)
    historico = motorista.atribuicoes.select_related('veiculo').all()
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


@login_required
@exige_escrita
def nova_atribuicao(request):
    """Vincula um motorista a um veiculo. Ao abrir um vinculo (sem data de fim),
    encerra automaticamente o vinculo anterior em aberto tanto do mesmo veiculo
    quanto do mesmo motorista (cada veiculo tem um motorista e cada motorista
    tem um veiculo por vez)."""
    org = organizacao_do(request.user)
    inicial = {}
    veiculo_id = request.GET.get('veiculo')
    if veiculo_id:
        inicial['veiculo'] = veiculo_id
    form = AtribuicaoVeiculoForm(request.POST or None, organizacao=org, initial=inicial)
    if request.method == 'POST' and form.is_valid():
        atrib = form.save()
        if atrib.data_fim is None:
            from django.db.models import Q
            # Encerra vinculos abertos do mesmo veiculo OU do mesmo motorista.
            AtribuicaoVeiculo.objects.filter(
                Q(veiculo=atrib.veiculo) | Q(motorista=atrib.motorista),
                data_fim__isnull=True,
            ).exclude(pk=atrib.pk).update(
                data_fim=atrib.data_inicio - timedelta(days=1))
        messages.success(request, 'Motorista vinculado ao veículo.')
        return redirect('detalhes_veiculo', veiculo_id=atrib.veiculo_id)
    return render(request, 'motoristas/form.html',
                  {'form': form, 'titulo': 'Vincular motorista a veículo'})


@login_required
@exige_escrita
@require_POST
def encerrar_atribuicao(request, pk):
    atrib = get_object_or_404(
        AtribuicaoVeiculo, pk=pk, veiculo__organizacao=organizacao_do(request.user))
    if atrib.data_fim is None:
        atrib.data_fim = timezone.now().date()
        atrib.save(update_fields=['data_fim'])
        messages.success(request, 'Vínculo encerrado.')
    return redirect('detalhes_veiculo', veiculo_id=atrib.veiculo_id)


@login_required
@exige_escrita
@require_POST
def excluir_atribuicao(request, pk):
    atrib = get_object_or_404(
        AtribuicaoVeiculo, pk=pk, veiculo__organizacao=organizacao_do(request.user))
    veiculo_id = atrib.veiculo_id
    atrib.delete()
    messages.success(request, 'Vínculo removido.')
    return redirect('detalhes_veiculo', veiculo_id=veiculo_id)


def _alocacoes_na_data(org, data):
    """Vinculos ativos em uma data: data_inicio <= data e (sem fim ou fim >= data)."""
    return (
        AtribuicaoVeiculo.objects
        .filter(veiculo__organizacao=org, data_inicio__lte=data)
        .filter(Q(data_fim__isnull=True) | Q(data_fim__gte=data))
        .select_related('veiculo', 'motorista')
        .order_by('veiculo__marca', 'veiculo__modelo')
    )


@login_required
@exige_gestor
def relatorio_motoristas(request):
    """Mostra qual motorista estava em qual veiculo em uma data de referencia."""
    org = organizacao_do(request.user)
    data_str = request.GET.get('data') or timezone.now().date().isoformat()
    try:
        data = timezone.datetime.fromisoformat(data_str).date()
    except ValueError:
        data = timezone.now().date()

    alocacoes = _alocacoes_na_data(org, data)

    if request.GET.get('formato') == 'csv':
        return _exportar_alocacoes_csv(alocacoes, data)

    # Veiculos sem motorista atribuido na data.
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
    escritor.writerow(['Data de referência', 'Veículo', 'Placa', 'Motorista',
                       'CNH', 'Início do vínculo', 'Fim do vínculo'])
    for a in alocacoes:
        escritor.writerow([
            data.strftime('%d/%m/%Y'),
            f'{a.veiculo.marca} {a.veiculo.modelo}',
            a.veiculo.placa,
            a.motorista.nome,
            a.motorista.cnh,
            a.data_inicio.strftime('%d/%m/%Y'),
            a.data_fim.strftime('%d/%m/%Y') if a.data_fim else 'em aberto',
        ])
    return resposta
