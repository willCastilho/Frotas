from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from carro.forms import (
    AbastecimentoForm,
    DocumentoForm,
    PlanoManutencaoForm,
    RegistroQuilometragemForm,
)
from carro.models import (
    Abastecimento,
    Documento,
    PlanoManutencao,
    RegistroQuilometragem,
    Veiculo,
)
from contas.utils import (
    exige_escrita,
    organizacao_do,
    perfil_do,
    pode_lancar_no_veiculo,
)


def _criar(request, veiculo_id, form_class, titulo, sucesso, operador_ok=False):
    veiculo = get_object_or_404(
        Veiculo, id=veiculo_id, organizacao=organizacao_do(request.user))
    # operador_ok: operador pode lancar no seu proprio veiculo; caso contrario,
    # a acao e restrita ao gestor da organizacao.
    if operador_ok:
        permitido = pode_lancar_no_veiculo(request.user, veiculo)
    else:
        perfil = perfil_do(request.user)
        permitido = bool(perfil and perfil.pode_administrar)
    if not permitido:
        messages.error(request, 'Você não tem permissão para esta ação.')
        return redirect('home')

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
                  'Novo Abastecimento', 'Abastecimento registrado com sucesso!',
                  operador_ok=True)


@login_required
def novo_registro_km(request, veiculo_id):
    return _criar(request, veiculo_id, RegistroQuilometragemForm,
                  'Novo Registro de Quilometragem', 'Quilometragem registrada!',
                  operador_ok=True)


@login_required
def novo_plano_manutencao(request, veiculo_id):
    return _criar(request, veiculo_id, PlanoManutencaoForm,
                  'Novo Plano de Manutenção', 'Plano de manutenção criado!')


@login_required
def novo_documento(request, veiculo_id):
    return _criar(request, veiculo_id, DocumentoForm,
                  'Novo Documento', 'Documento cadastrado!')


def _excluir(request, model, pk, sucesso):
    obj = get_object_or_404(
        model, pk=pk, veiculo__organizacao=organizacao_do(request.user))
    veiculo_id = obj.veiculo_id
    obj.delete()
    messages.success(request, sucesso)
    return redirect('detalhes_veiculo', veiculo_id=veiculo_id)


@login_required
@exige_escrita
@require_POST
def excluir_abastecimento(request, pk):
    return _excluir(request, Abastecimento, pk, 'Abastecimento excluído.')


@login_required
@exige_escrita
@require_POST
def excluir_registro_km(request, pk):
    return _excluir(request, RegistroQuilometragem, pk, 'Registro excluído.')


@login_required
@exige_escrita
@require_POST
def excluir_plano_manutencao(request, pk):
    return _excluir(request, PlanoManutencao, pk, 'Plano excluído.')


@login_required
@exige_escrita
@require_POST
def excluir_documento(request, pk):
    return _excluir(request, Documento, pk, 'Documento excluído.')
