from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from carro.forms import CustoForm
from carro.models import Custo, Veiculo


@login_required
def novo_custo(request, veiculo_id):
    veiculo = get_object_or_404(Veiculo, id=veiculo_id)
    form = CustoForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        custo = form.save(commit=False)
        custo.veiculo = veiculo
        custo.save()
        messages.success(request, 'Custo cadastrado com sucesso!')
        return redirect('detalhes_veiculo', veiculo_id=veiculo.id)
    return render(request, 'novo_custo.html', {'form': form, 'veiculo': veiculo})


@login_required
def editar_custo(request, custo_id):
    custo = get_object_or_404(Custo, id=custo_id)
    veiculo = custo.veiculo
    form = CustoForm(request.POST or None, instance=custo)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Custo editado com sucesso!')
        return redirect('detalhes_veiculo', veiculo_id=veiculo.id)
    return render(request, 'editar_custo.html',
                  {'form': form, 'custo': custo, 'veiculo': veiculo})


@login_required
@require_POST
def deletar_custo(request, custo_id):
    custo = get_object_or_404(Custo, id=custo_id)
    veiculo_id = custo.veiculo.id
    custo.delete()
    messages.success(request, 'Custo deletado com sucesso!')
    return redirect('detalhes_veiculo', veiculo_id=veiculo_id)
