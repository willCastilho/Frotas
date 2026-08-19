from django.contrib import admin
from . import models

@admin.register(models.Veiculo)
class VeiculoAdmin(admin.ModelAdmin):
    list_display = ('modelo', 'marca', 'ano', 'cor', 'Data_compra', 'data_cadastro')
    list_filter = ('marca', 'ano', 'status')
    search_fields = ('modelo', 'marca')
    date_hierarchy = 'data_cadastro'
    list_display_links = ('modelo', 'marca')

@admin.register(models.Custo)
class CustoAdmin(admin.ModelAdmin):
    list_display = ('veiculo', 'tipo', 'descricao', 'valor', 'data')
    list_filter = ('veiculo', 'tipo', 'data')
    search_fields = ('veiculo__modelo', 'tipo', 'descricao')
    date_hierarchy = 'data'

