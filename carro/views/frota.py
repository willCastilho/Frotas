from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from carro.forms import (
    AbastecimentoForm,
    PlanoManutencaoForm,
    RegistroQuilometragemForm,
)
from carro.models import (
    Abastecimento,
    PlanoManutencao,
    RegistroQuilometragem,
    Veiculo,
)


def _criar(request, veiculo_id, form_class, titulo, sucesso):
    veiculo = get_object_or_404(Veiculo, id=veiculo_id)
    form = form_class(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        obj = form.save(commit=False)
        obj.veiculo = veiculo
        obj.save()
        messages.success(request, sucesso)
        return redirect('detalhes_veiculo', veiculo_id=veiculo.id)
    return render(request, 'form_generico.html',
                  {'form': form, 'veiculo': veiculo, 'titulo': titulo})


@login_required
def novo_abastecimento(request, veiculo_id):
    return _criar(request, veiculo_id, AbastecimentoForm,
                  'Novo Abastecimento', 'Abastecimento registrado com sucesso!')


@login_required
def novo_registro_km(request, veiculo_id):
    return _criar(request, veiculo_id, RegistroQuilometragemForm,
                  'Novo Registro de Quilometragem', 'Quilometragem registrada!')


@login_required
def novo_plano_manutencao(request, veiculo_id):
    return _criar(request, veiculo_id, PlanoManutencaoForm,
                  'Novo Plano de Manutenção', 'Plano de manutenção criado!')


def _excluir(request, model, pk, sucesso):
    obj = get_object_or_404(model, pk=pk)
    veiculo_id = obj.veiculo_id
    obj.delete()
    messages.success(request, sucesso)
    return redirect('detalhes_veiculo', veiculo_id=veiculo_id)


@login_required
@require_POST
def excluir_abastecimento(request, pk):
    return _excluir(request, Abastecimento, pk, 'Abastecimento excluído.')


@login_required
@require_POST
def excluir_registro_km(request, pk):
    return _excluir(request, RegistroQuilometragem, pk, 'Registro excluído.')


@login_required
@require_POST
def excluir_plano_manutencao(request, pk):
    return _excluir(request, PlanoManutencao, pk, 'Plano excluído.')
