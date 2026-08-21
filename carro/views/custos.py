from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from carro.forms import CustoForm
from carro.models import Custo, Veiculo
from contas.utils import exige_escrita, organizacao_do


def _veiculo_da_org(request, veiculo_id):
    return get_object_or_404(
        Veiculo, id=veiculo_id, organizacao=organizacao_do(request.user))


def _custo_da_org(request, custo_id):
    return get_object_or_404(
        Custo, id=custo_id, veiculo__organizacao=organizacao_do(request.user))


@login_required
@exige_escrita
def novo_custo(request, veiculo_id):
    veiculo = _veiculo_da_org(request, veiculo_id)
    form = CustoForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        custo = form.save(commit=False)
        custo.veiculo = veiculo
        custo.save()
        messages.success(request, 'Custo cadastrado com sucesso!')
        return redirect('detalhes_veiculo', veiculo_id=veiculo.id)
    return render(request, 'novo_custo.html', {'form': form, 'veiculo': veiculo})


@login_required
@exige_escrita
def editar_custo(request, custo_id):
    custo = _custo_da_org(request, custo_id)
    veiculo = custo.veiculo
    if hasattr(custo, 'abastecimento'):
        messages.info(request, 'Este custo vem de um abastecimento; edite pelo abastecimento.')
        return redirect('detalhes_veiculo', veiculo_id=veiculo.id)
    form = CustoForm(request.POST or None, request.FILES or None, instance=custo)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Custo editado com sucesso!')
        return redirect('detalhes_veiculo', veiculo_id=veiculo.id)
    return render(request, 'editar_custo.html',
                  {'form': form, 'custo': custo, 'veiculo': veiculo})


@login_required
@exige_escrita
@require_POST
def deletar_custo(request, custo_id):
    custo = _custo_da_org(request, custo_id)
    veiculo_id = custo.veiculo.id
    if hasattr(custo, 'abastecimento'):
        messages.info(request, 'Este custo vem de um abastecimento; exclua pelo abastecimento.')
        return redirect('detalhes_veiculo', veiculo_id=veiculo_id)
    custo.delete()
    messages.success(request, 'Custo deletado com sucesso!')
    return redirect('detalhes_veiculo', veiculo_id=veiculo_id)
