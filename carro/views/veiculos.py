from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from carro.forms import VeiculoForm
from carro.models import Custo, Veiculo, comparacao_custos
from contas.utils import exige_escrita, organizacao_do

VEICULOS_POR_PAGINA = 9


def _veiculos_da_org(request):
    """Queryset base isolado pela organizacao do usuario logado."""
    return Veiculo.objects.filter(organizacao=organizacao_do(request.user))


@login_required
def home(request):
    status_filter = request.GET.get('status', 'todos')
    search_query = request.GET.get('search', '').strip()

    carros = _veiculos_da_org(request).com_custos_mensais().order_by('marca', 'modelo')

    if status_filter != 'todos':
        carros = carros.filter(status=status_filter)

    if search_query:
        carros = carros.filter(
            Q(marca__icontains=search_query) |
            Q(modelo__icontains=search_query) |
            Q(placa__icontains=search_query)
        )

    paginator = Paginator(carros, VEICULOS_POR_PAGINA)
    page_obj = paginator.get_page(request.GET.get('page'))

    carros_com_custos = []
    for carro in page_obj:
        atual = float(carro.custo_atual or 0)
        anterior = float(carro.custo_anterior or 0)
        meta = float(carro.meta_custo_mensal or 0)
        meta_info = None
        if meta > 0:
            pct = round(atual / meta * 100)
            cor = 'green' if pct < 80 else 'yellow' if pct <= 100 else 'red'
            meta_info = {'meta': meta, 'pct': pct, 'pct_barra': min(pct, 100), 'cor': cor}
        carros_com_custos.append({
            'id': carro.id,
            'marca': carro.marca,
            'modelo': carro.modelo,
            'ano': carro.ano,
            'cor': carro.cor,
            'placa': carro.placa,
            'status': carro.status,
            'picture': carro.picture,
            'custo_mes_atual': atual,
            'comparacao': comparacao_custos(atual, anterior),
            'meta': meta_info,
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
    veiculo = get_object_or_404(_veiculos_da_org(request), id=veiculo_id)
    custos = Custo.objects.filter(veiculo=veiculo).order_by('-data')

    km_atual = veiculo.km_atual()
    planos = [
        {'obj': plano, 'status': plano.status(km_atual)}
        for plano in veiculo.planos_manutencao.all()
    ]
    documentos = [
        {'obj': doc, 'status': doc.status()}
        for doc in veiculo.documentos.all()
    ]

    context = {
        'veiculo': veiculo,
        'custos': custos,
        'custo_mes_atual': veiculo.custo_mes_atual(),
        'custo_mes_anterior': veiculo.custo_mes_anterior(),
        'comparacao': veiculo.comparacao_custos(),
        'km_atual': km_atual,
        'consumo_medio': veiculo.consumo_medio(),
        'custo_por_km': veiculo.custo_por_km(),
        'abastecimentos': veiculo.abastecimentos.all()[:10],
        'registros_km': veiculo.registros_km.all()[:10],
        'planos': planos,
        'documentos': documentos,
    }
    return render(request, 'detalhes_veiculo.html', context)


@login_required
@exige_escrita
def novo_veiculo(request):
    org = organizacao_do(request.user)
    if org and org.atingiu_limite_veiculos():
        messages.error(
            request,
            'Você atingiu o limite de veículos do seu plano. '
            'Faça upgrade para cadastrar mais.'
        )
        return redirect('home')

    form = VeiculoForm(request.POST or None, request.FILES or None, organizacao=org)
    if request.method == 'POST' and form.is_valid():
        veiculo = form.save(commit=False)
        veiculo.organizacao = org
        veiculo.save()
        messages.success(request, 'Veículo cadastrado com sucesso!')
        return redirect('home')
    return render(request, 'novo_veiculo.html', {'form': form})


@login_required
@exige_escrita
def editar_veiculo(request, veiculo_id):
    veiculo = get_object_or_404(_veiculos_da_org(request), id=veiculo_id)
    form = VeiculoForm(request.POST or None, request.FILES or None,
                       instance=veiculo, organizacao=organizacao_do(request.user))
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Veículo atualizado com sucesso!')
        return redirect('detalhes_veiculo', veiculo_id=veiculo.id)
    return render(request, 'editar_veiculo.html', {'form': form, 'veiculo': veiculo})


@login_required
@exige_escrita
@require_POST
def excluir_veiculo(request, veiculo_id):
    veiculo = get_object_or_404(_veiculos_da_org(request), id=veiculo_id)
    veiculo.delete()
    messages.success(request, 'Veículo excluído com sucesso!')
    return redirect('home')
