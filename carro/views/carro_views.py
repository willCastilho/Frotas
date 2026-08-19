from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from carro.models import Veiculo, Custo
from django.http import HttpResponse
from django.utils import timezone

def home(request):

    status_filter = request.GET.get('status', 'todos')
    search_query = request.GET.get('search', '')
    
    carros = Veiculo.objects.all()

    if status_filter != 'todos':
        carros = carros.filter(status=status_filter)
    
    if search_query:
        from django.db.models import Q
        carros = carros.filter(
            Q(marca__icontains=search_query) |
            Q(modelo__icontains=search_query) 
        )
        
    
    carros_com_custos = []
    for carro in carros:
        custo_mes_atual = carro.custo_mes_atual()
        comparacao = carro.comparacao_custos()
        
        carros_com_custos.append({
            'id':carro.id,
            'marca': carro.marca,
            'modelo': carro.modelo,
            'ano': carro.ano,
            'cor': carro.cor,
            'status': carro.status,
            'picture': carro.picture,
            'custo_mes_atual': custo_mes_atual,
            'comparacao': comparacao,
        })
            
        context = {
        'carros': carros_com_custos,
        'status_filter': status_filter,
        'search_query': search_query,
    }
    
    return render(
        request,
        'base.html', context)

def detalhes_veiculo(request, veiculo_id):
    veiculo = get_object_or_404(Veiculo, id=veiculo_id)
    custos = Custo.objects.filter(veiculo=veiculo).order_by('-data')

    custo_mes_atual = veiculo.custo_mes_atual()
    custo_mes_anterior = veiculo.custo_mes_anterior()
    comparacao = veiculo.comparacao_custos()
    
    context = {
        'veiculo': veiculo,
        'custos': custos,
        'custo_mes_atual': custo_mes_atual,
        'custo_mes_anterior': custo_mes_anterior,
        'comparacao': comparacao,
    }
    
    return render(request, 'detalhes_veiculo.html', context)

def novo_custo(request, veiculo_id):
    veiculo = get_object_or_404(Veiculo, id=veiculo_id)
    
    if request.method == 'POST':
        tipo = request.POST.get('tipo')
        descricao = request.POST.get('descricao')
        valor = request.POST.get('valor')
        data = request.POST.get('data')
        
        if tipo and descricao and valor and data:
            Custo.objects.create(
                veiculo=veiculo,
                tipo=tipo,
                descricao=descricao,
                valor=valor,
                data=data
            )
            messages.success(request, 'Custo cadastrado com sucesso!')
            return redirect('detalhes_veiculo', veiculo_id=veiculo.id)
        else:
            messages.error(request, 'Preencha todos os campos!')
    
    context = {
        'veiculo': veiculo,
        'tipo_choices': Custo.TIPO_CHOICES,
    }
    
    return render(request, "novo_custo.html", context)

def editar_custo(request, custo_id):
    custo = get_object_or_404(Custo, id=custo_id)
    veiculo = custo.veiculo

    if request.method == 'POST':
        tipo = request.POST.get('tipo')
        descricao = request.POST.get('descricao')
        valor = request.POST.get('valor')
        data = request.POST.get('data')

        if tipo and descricao and valor and data:
            custo.tipo = tipo
            custo.descricao = descricao
            custo.valor = valor
            custo.data = data
            custo.save()

            messages.success(request, 'Custo editado com sucesso!')
            return redirect('detalhes_veiculo', veiculo_id=veiculo.id)
        else:
            messages.error(request, 'Preencha todos os campos!')

    context = {
        'custo': custo,
        'veiculo': veiculo,
        'tipo_choices': Custo.TIPO_CHOICES,
    }

    return render(request, 'editar_custo.html', context)

def deletar_custo(request, custo_id):
    custo = get_object_or_404(Custo, id=custo_id)
    veiculo_id = custo.veiculo.id
    custo.delete()
    messages.success(request, 'Custo deletado com sucesso!')
    return redirect('detalhes_veiculo', veiculo_id=veiculo_id)

def novo_veiculo(request):
    if request.method == 'POST':
        modelo = request.POST.get('modelo')
        marca = request.POST.get('marca')
        ano = request.POST.get('ano')
        cor = request.POST.get('cor')
        data_compra = request.POST.get('data_compra')
        status = request.POST.get('status')
        picture = request.FILES.get('picture')
        
        if modelo and marca and ano and cor and data_compra and status:
            Veiculo.objects.create(
                modelo=modelo,
                marca=marca,
                ano=ano,
                cor=cor,
                Data_compra=data_compra,
                status=status,
                picture=picture
            )
            messages.success(request, 'Veículo cadastrado com sucesso!')
            return redirect('home')
        else:
            messages.error(request, 'Preencha todos os campos obrigatórios!')
    
    context = {
        'status_choices': Veiculo.STATUS_CHOICES,
    }
    
    return render(request, "novo_veiculo.html", context)

def editar_veiculo(request, veiculo_id):
    veiculo = get_object_or_404(Veiculo, id=veiculo_id)
    
    if request.method == 'POST':
        veiculo.modelo = request.POST.get('modelo')
        veiculo.marca = request.POST.get('marca')
        veiculo.ano = request.POST.get('ano')
        veiculo.cor = request.POST.get('cor')
        veiculo.Data_compra = request.POST.get('data_compra')
        veiculo.status = request.POST.get('status')
        
        if request.FILES.get('picture'):
            veiculo.picture = request.FILES.get('picture')
        
        veiculo.save()
        messages.success(request, 'Veículo atualizado com sucesso!')
        return redirect('detalhes_veiculo', veiculo_id=veiculo.id)
    
    context = {
        'veiculo': veiculo,
        'status_choices': Veiculo.STATUS_CHOICES,
    }
    
    return render(request, "editar_veiculo.html", context)

def excluir_veiculo(request, veiculo_id):
    veiculo = get_object_or_404(Veiculo, id=veiculo_id)
    veiculo.delete()
    messages.success(request, 'Veículo excluído com sucesso!')
    return redirect('home')