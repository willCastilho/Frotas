from django.urls import path

from contas import views

urlpatterns = [
    path('cadastro/', views.cadastro, name='cadastro'),
    path('conta/criar-organizacao/', views.criar_organizacao, name='criar_organizacao'),
    path('conta/usuarios/', views.usuarios, name='usuarios'),
    path('conta/usuarios/<int:perfil_id>/papel/', views.alterar_papel, name='alterar_papel'),
    path('conta/usuarios/<int:perfil_id>/remover/', views.remover_usuario, name='remover_usuario'),
    path('conta/', views.conta, name='conta'),
    path('conta/logs/', views.logs, name='logs'),
    path('termos/', views.termos, name='termos'),
    path('privacidade/', views.privacidade, name='privacidade'),

    # Administrador global do sistema
    path('sistema/', views.painel_admin, name='painel_admin'),
    path('sistema/logs/', views.logs_sistema, name='logs_sistema'),
    path('sistema/org/<int:org_id>/', views.admin_organizacao, name='admin_organizacao'),
    path('sistema/impersonar/<int:perfil_id>/', views.impersonar, name='impersonar'),
    path('sistema/sair-simulacao/', views.sair_impersonacao, name='sair_impersonacao'),

    # CRUD do admin global
    path('sistema/org/nova/', views.nova_organizacao, name='nova_organizacao_admin'),
    path('sistema/org/<int:org_id>/editar/', views.editar_organizacao, name='editar_organizacao'),
    path('sistema/org/<int:org_id>/excluir/', views.excluir_organizacao, name='excluir_organizacao'),
    path('sistema/org/<int:org_id>/usuario/novo/', views.novo_usuario_admin, name='novo_usuario_admin'),
    path('sistema/usuario/<int:perfil_id>/editar/', views.editar_usuario_admin, name='editar_usuario_admin'),
    path('sistema/usuario/<int:perfil_id>/excluir/', views.excluir_usuario_admin, name='excluir_usuario_admin'),
    path('sistema/org/<int:org_id>/veiculo/novo/', views.novo_veiculo_admin, name='novo_veiculo_admin'),
    path('sistema/veiculo/<int:veiculo_id>/editar/', views.editar_veiculo_admin, name='editar_veiculo_admin'),
    path('sistema/veiculo/<int:veiculo_id>/excluir/', views.excluir_veiculo_admin, name='excluir_veiculo_admin'),
]
