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
]
