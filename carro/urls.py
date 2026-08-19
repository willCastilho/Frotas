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
]