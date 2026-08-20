from django.urls import path
from carro import views as carro_views


urlpatterns = [
    path('', carro_views.home, name='home'),
    path('veiculo/<int:veiculo_id>/detalhes/', carro_views.detalhes_veiculo, name='detalhes_veiculo'),
    path('veiculo/<int:veiculo_id>/novo-custo/', carro_views.novo_custo, name='novo_custo'),
    path('custo/<int:custo_id>/editar/', carro_views.editar_custo, name='editar_custo'),
    path('custo/<int:custo_id>/deletar/', carro_views.deletar_custo, name='deletar_custo'),
    path('veiculo/novo/', carro_views.novo_veiculo, name='novo_veiculo'),
    path('veiculo/<int:veiculo_id>/editar/', carro_views.editar_veiculo, name='editar_veiculo'),
    path('veiculo/<int:veiculo_id>/excluir/', carro_views.excluir_veiculo, name='excluir_veiculo'),

    # Fase 3 - dominio da frota
    path('veiculo/<int:veiculo_id>/novo-abastecimento/', carro_views.novo_abastecimento, name='novo_abastecimento'),
    path('veiculo/<int:veiculo_id>/novo-km/', carro_views.novo_registro_km, name='novo_registro_km'),
    path('veiculo/<int:veiculo_id>/novo-plano/', carro_views.novo_plano_manutencao, name='novo_plano_manutencao'),
    path('abastecimento/<int:pk>/excluir/', carro_views.excluir_abastecimento, name='excluir_abastecimento'),
    path('km/<int:pk>/excluir/', carro_views.excluir_registro_km, name='excluir_registro_km'),
    path('plano/<int:pk>/excluir/', carro_views.excluir_plano_manutencao, name='excluir_plano_manutencao'),
]
