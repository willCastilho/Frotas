from django.urls import path

from contas import views

urlpatterns = [
    path('cadastro/', views.cadastro, name='cadastro'),
    path('conta/criar-organizacao/', views.criar_organizacao, name='criar_organizacao'),
    path('conta/usuarios/', views.usuarios, name='usuarios'),
    path('conta/usuarios/<int:perfil_id>/papel/', views.alterar_papel, name='alterar_papel'),
    path('conta/usuarios/<int:perfil_id>/remover/', views.remover_usuario, name='remover_usuario'),
    path('conta/', views.conta, name='conta'),
    path('termos/', views.termos, name='termos'),
    path('privacidade/', views.privacidade, name='privacidade'),
]
