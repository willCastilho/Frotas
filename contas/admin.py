from django.contrib import admin

from auditlog.registry import auditlog

from contas.models import Organizacao, PerfilUsuario, Plano


@admin.register(Plano)
class PlanoAdmin(admin.ModelAdmin):
    list_display = ('nome', 'slug', 'preco_mensal', 'limite_veiculos', 'ativo')
    prepopulated_fields = {'slug': ('nome',)}


@admin.register(Organizacao)
class OrganizacaoAdmin(admin.ModelAdmin):
    list_display = ('nome', 'plano', 'assinatura_ativa', 'assinatura_valida_ate', 'criado_em')
    list_filter = ('plano', 'assinatura_ativa')
    search_fields = ('nome',)


@admin.register(PerfilUsuario)
class PerfilUsuarioAdmin(admin.ModelAdmin):
    list_display = ('user', 'organizacao', 'papel')
    list_filter = ('organizacao', 'papel')
    search_fields = ('user__username', 'user__email')


for _m in (Organizacao, PerfilUsuario, Plano):
    auditlog.register(_m)
