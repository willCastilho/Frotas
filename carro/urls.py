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
    path('veiculo/<int:veiculo_id>/novo-documento/', carro_views.novo_documento, name='novo_documento'),
    path('abastecimento/<int:pk>/excluir/', carro_views.excluir_abastecimento, name='excluir_abastecimento'),
    path('km/<int:pk>/excluir/', carro_views.excluir_registro_km, name='excluir_registro_km'),
    path('plano/<int:pk>/excluir/', carro_views.excluir_plano_manutencao, name='excluir_plano_manutencao'),
    path('documento/<int:pk>/excluir/', carro_views.excluir_documento, name='excluir_documento'),

    # Fase 4 - camada gerencial
    path('dashboard/', carro_views.dashboard, name='dashboard'),
    path('relatorios/', carro_views.relatorios, name='relatorios'),
    path('relatorios/exportar/', carro_views.exportar_custos, name='exportar_custos'),
    path('relatorios/motoristas/', carro_views.relatorio_motoristas, name='relatorio_motoristas'),

    # Motoristas e vinculo motorista x veiculo
    path('motoristas/', carro_views.motoristas, name='motoristas'),
    path('motoristas/novo/', carro_views.novo_motorista, name='novo_motorista'),
    path('motoristas/<int:motorista_id>/', carro_views.detalhes_motorista, name='detalhes_motorista'),
    path('motoristas/<int:motorista_id>/editar/', carro_views.editar_motorista, name='editar_motorista'),
    path('motoristas/<int:motorista_id>/excluir/', carro_views.excluir_motorista, name='excluir_motorista'),
    path('atribuicao/nova/', carro_views.nova_atribuicao, name='nova_atribuicao'),
    path('atribuicao/<int:pk>/encerrar/', carro_views.encerrar_atribuicao, name='encerrar_atribuicao'),
    path('atribuicao/<int:pk>/excluir/', carro_views.excluir_atribuicao, name='excluir_atribuicao'),
]
