from django.contrib import admin
from . import models

@admin.register(models.Veiculo)
class VeiculoAdmin(admin.ModelAdmin):
    list_display = ('modelo', 'marca', 'placa', 'ano', 'organizacao', 'status')
    list_filter = ('organizacao', 'marca', 'ano', 'status', 'combustivel')
    search_fields = ('modelo', 'marca', 'placa', 'renavam', 'chassi')
    date_hierarchy = 'data_cadastro'
    list_display_links = ('modelo', 'marca')

@admin.register(models.Custo)
class CustoAdmin(admin.ModelAdmin):
    list_display = ('veiculo', 'tipo', 'descricao', 'valor', 'data', 'fornecedor')
    list_filter = ('veiculo', 'tipo', 'forma_pagamento', 'data')
    search_fields = ('veiculo__modelo', 'tipo', 'descricao', 'fornecedor')
    date_hierarchy = 'data'


@admin.register(models.Abastecimento)
class AbastecimentoAdmin(admin.ModelAdmin):
    list_display = ('veiculo', 'data', 'quilometragem', 'litros',
                    'valor_total', 'tipo_combustivel')
    list_filter = ('veiculo', 'tipo_combustivel', 'data')
    search_fields = ('veiculo__modelo', 'posto')
    date_hierarchy = 'data'


@admin.register(models.RegistroQuilometragem)
class RegistroQuilometragemAdmin(admin.ModelAdmin):
    list_display = ('veiculo', 'data', 'quilometragem', 'origem')
    list_filter = ('veiculo', 'data')
    date_hierarchy = 'data'


@admin.register(models.PlanoManutencao)
class PlanoManutencaoAdmin(admin.ModelAdmin):
    list_display = ('veiculo', 'descricao', 'intervalo_km', 'intervalo_dias',
                    'km_referencia', 'data_referencia')
    list_filter = ('veiculo',)
    search_fields = ('veiculo__modelo', 'descricao')


@admin.register(models.Documento)
class DocumentoAdmin(admin.ModelAdmin):
    list_display = ('veiculo', 'tipo', 'vencimento', 'observacao')
    list_filter = ('tipo', 'vencimento')
    search_fields = ('veiculo__modelo', 'veiculo__placa')
    date_hierarchy = 'vencimento'


@admin.register(models.Motorista)
class MotoristaAdmin(admin.ModelAdmin):
    list_display = ('nome', 'cnh', 'cnh_categoria', 'cnh_validade',
                    'organizacao', 'status')
    list_filter = ('organizacao', 'status', 'cnh_categoria')
    search_fields = ('nome', 'cpf', 'cnh')


@admin.register(models.AtribuicaoVeiculo)
class AtribuicaoVeiculoAdmin(admin.ModelAdmin):
    list_display = ('motorista', 'veiculo', 'data_inicio', 'data_fim')
    list_filter = ('data_inicio',)
    search_fields = ('motorista__nome', 'veiculo__modelo', 'veiculo__placa')
    date_hierarchy = 'data_inicio'

