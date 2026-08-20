from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from carro.forms import VeiculoForm
from carro.models import Custo, Veiculo, comparacao_custos

VEICULOS_POR_PAGINA = 9


@login_required
def home(request):
    status_filter = request.GET.get('status', 'todos')
    search_query = request.GET.get('search', '').strip()

    carros = Veiculo.objects.com_custos_mensais().order_by('marca', 'modelo')

    if status_filter != 'todos':
        carros = carros.filter(status=status_filter)

    if search_query:
        carros = carros.filter(
            Q(marca__icontains=search_query) |
            Q(modelo__icontains=search_query)
        )

    paginator = Paginator(carros, VEICULOS_POR_PAGINA)
    page_obj = paginator.get_page(request.GET.get('page'))

    carros_com_custos = []
    for carro in page_obj:
        atual = float(carro.custo_atual or 0)
        anterior = float(carro.custo_anterior or 0)
        carros_com_custos.append({
            'id': carro.id,
            'marca': carro.marca,
            'modelo': carro.modelo,
            'ano': carro.ano,
            'cor': carro.cor,
            'status': carro.status,
            'picture': carro.picture,
            'custo_mes_atual': atual,
            'comparacao': comparacao_custos(atual, anterior),
        })

    context = {
        'carros': carros_com_custos,
        'page_obj': page_obj,
        'status_filter': status_filter,
        'search_query': search_query,
    }
    return render(request, 'base.html', context)


@login_required
def detalhes_veiculo(request, veiculo_id):
    veiculo = get_object_or_404(Veiculo, id=veiculo_id)
    custos = Custo.objects.filter(veiculo=veiculo).order_by('-data')

    context = {
        'veiculo': veiculo,
        'custos': custos,
        'custo_mes_atual': veiculo.custo_mes_atual(),
        'custo_mes_anterior': veiculo.custo_mes_anterior(),
        'comparacao': veiculo.comparacao_custos(),
    }
    return render(request, 'detalhes_veiculo.html', context)


@login_required
def novo_veiculo(request):
    form = VeiculoForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Veículo cadastrado com sucesso!')
        return redirect('home')
    return render(request, 'novo_veiculo.html', {'form': form})


@login_required
def editar_veiculo(request, veiculo_id):
    veiculo = get_object_or_404(Veiculo, id=veiculo_id)
    form = VeiculoForm(request.POST or None, request.FILES or None, instance=veiculo)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Veículo atualizado com sucesso!')
        return redirect('detalhes_veiculo', veiculo_id=veiculo.id)
    return render(request, 'editar_veiculo.html', {'form': form, 'veiculo': veiculo})


@login_required
@require_POST
def excluir_veiculo(request, veiculo_id):
    veiculo = get_object_or_404(Veiculo, id=veiculo_id)
    veiculo.delete()
    messages.success(request, 'Veículo excluído com sucesso!')
    return redirect('home')
