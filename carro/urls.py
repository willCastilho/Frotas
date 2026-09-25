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
    path('financeiro/', carro_views.financeiro, name='financeiro'),
    path('relatorios/', carro_views.relatorios, name='relatorios'),
    path('relatorios/exportar/', carro_views.exportar_custos, name='exportar_custos'),
    path('relatorios/motoristas/', carro_views.relatorio_motoristas, name='relatorio_motoristas'),

    # Motoristas e vinculo motorista x veiculo
    path('motoristas/', carro_views.motoristas, name='motoristas'),
    path('motoristas/novo/', carro_views.novo_motorista, name='novo_motorista'),
    path('motoristas/<int:motorista_id>/', carro_views.detalhes_motorista, name='detalhes_motorista'),
    path('motoristas/<int:motorista_id>/editar/', carro_views.editar_motorista, name='editar_motorista'),
    path('motoristas/<int:motorista_id>/excluir/', carro_views.excluir_motorista, name='excluir_motorista'),
    path('escala/', carro_views.escala, name='escala'),
    path('escala/montar/', carro_views.montar_escala, name='montar_escala'),
    path('escala/<int:pk>/remover/', carro_views.remover_escala, name='remover_escala'),
    path('escala/<int:pk>/', carro_views.detalhes_escala, name='detalhes_escala'),

    # Pre-agendamento de veiculos
    path('agendamento/cadastro/<uuid:token>/', carro_views.cadastro_solicitante, name='cadastro_solicitante'),
    path('agendamento/minhas/', carro_views.minhas_solicitacoes, name='minhas_solicitacoes'),
    path('agendamento/nova/', carro_views.nova_solicitacao, name='nova_solicitacao'),
    path('agendamento/<int:pk>/', carro_views.detalhes_solicitacao, name='detalhes_solicitacao'),
    path('agendamento/<int:pk>/cancelar/', carro_views.cancelar_solicitacao, name='cancelar_solicitacao'),
    path('agendamento/<int:pk>/retirar/', carro_views.iniciar_uso, name='iniciar_uso'),
    path('agendamento/<int:pk>/devolucao/', carro_views.registrar_devolucao, name='registrar_devolucao'),
    path('agendamento/gestor/', carro_views.solicitacoes_gestor, name='solicitacoes_gestor'),
    path('agendamento/gestor/agenda/', carro_views.agenda, name='agenda'),
    path('agendamento/gestor/<int:pk>/aprovar/', carro_views.aprovar_solicitacao, name='aprovar_solicitacao'),
    path('agendamento/gestor/<int:pk>/recusar/', carro_views.recusar_solicitacao, name='recusar_solicitacao'),
    path('agendamento/gestor/cadastros/', carro_views.cadastros_solicitantes, name='cadastros_solicitantes'),
    path('agendamento/gestor/cadastros/<int:pk>/decidir/', carro_views.decidir_cadastro, name='decidir_cadastro'),
    path('agendamento/gestor/solicitante/<int:pk>/', carro_views.detalhes_solicitante, name='detalhes_solicitante'),
]
