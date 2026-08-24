import uuid
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from carro.forms import CustoForm
from carro.models import Custo, Veiculo, somar_meses
from contas.utils import exige_escrita, organizacao_do, pode_lancar_no_veiculo


def _veiculo_da_org(request, veiculo_id):
    return get_object_or_404(
        Veiculo, id=veiculo_id, organizacao=organizacao_do(request.user))


def _custo_da_org(request, custo_id):
    return get_object_or_404(
        Custo, id=custo_id, veiculo__organizacao=organizacao_do(request.user))


def _gerar_serie(custo, veiculo, recorrencia, ocorrencias):
    """Gera a serie de custos recorrentes/parcelados a partir do lancamento base.

    - parcelado: divide o valor total em `ocorrencias` parcelas mensais.
    - mensal/anual: repete o mesmo valor a cada mes/ano.
    Retorna a quantidade de lancamentos criados.
    """
    grupo = uuid.uuid4().hex
    total = Decimal(str(custo.valor))
    passo_meses = 12 if recorrencia == 'anual' else 1

    if recorrencia == 'parcelado':
        parcela = (total / ocorrencias).quantize(Decimal('0.01'))
        valores = [parcela] * (ocorrencias - 1)
        valores.append(total - parcela * (ocorrencias - 1))  # ajuste do arredondamento
    else:
        valores = [total] * ocorrencias

    for i, valor in enumerate(valores):
        Custo.objects.create(
            veiculo=veiculo,
            tipo=custo.tipo,
            descricao=custo.descricao,
            valor=valor,
            data=somar_meses(custo.data, i * passo_meses),
            quilometragem=custo.quilometragem if i == 0 else None,
            fornecedor=custo.fornecedor,
            forma_pagamento=custo.forma_pagamento,
            comprovante=custo.comprovante if i == 0 else None,
            grupo=grupo,
            parcela_numero=i + 1,
            parcela_total=ocorrencias,
        )
    return len(valores)


@login_required
def novo_custo(request, veiculo_id):
    veiculo = _veiculo_da_org(request, veiculo_id)
    # Gestor lanca em qualquer veiculo da org; operador so no seu veiculo.
    if not pode_lancar_no_veiculo(request.user, veiculo):
        messages.error(request, 'Você não tem permissão para lançar neste veículo.')
        return redirect('home')
    form = CustoForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        custo = form.save(commit=False)
        custo.veiculo = veiculo
        recorrencia = form.cleaned_data.get('recorrencia') or 'nenhuma'
        ocorrencias = form.cleaned_data.get('ocorrencias') or 1
        if recorrencia != 'nenhuma' and ocorrencias > 1:
            qtd = _gerar_serie(custo, veiculo, recorrencia, ocorrencias)
            messages.success(request, f'{qtd} lançamentos cadastrados com sucesso!')
        else:
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
