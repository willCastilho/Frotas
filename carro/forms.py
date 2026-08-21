from django import forms

from carro.models import (
    Abastecimento,
    Custo,
    PlanoManutencao,
    RegistroQuilometragem,
    Veiculo,
)

_DATE = forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d')


class VeiculoForm(forms.ModelForm):
    class Meta:
        model = Veiculo
        fields = ['marca', 'modelo', 'ano', 'cor', 'placa', 'renavam', 'chassi',
                  'combustivel', 'data_compra', 'valor_aquisicao', 'status',
                  'meta_custo_mensal', 'observacoes', 'picture']
        widgets = {
            'data_compra': forms.DateInput(
                attrs={'type': 'date'}, format='%Y-%m-%d'
            ),
            'observacoes': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, organizacao=None, **kwargs):
        self.organizacao = organizacao
        super().__init__(*args, **kwargs)

    def clean_ano(self):
        ano = self.cleaned_data['ano']
        if ano < 1900 or ano > 2100:
            raise forms.ValidationError('Informe um ano entre 1900 e 2100.')
        return ano

    def clean_placa(self):
        placa = (self.cleaned_data.get('placa') or '').upper().strip()
        if placa and self.organizacao is not None:
            existentes = Veiculo.objects.filter(
                organizacao=self.organizacao, placa=placa)
            if self.instance and self.instance.pk:
                existentes = existentes.exclude(pk=self.instance.pk)
            if existentes.exists():
                raise forms.ValidationError('Já existe um veículo com esta placa.')
        return placa


class CustoForm(forms.ModelForm):
    class Meta:
        model = Custo
        fields = ['tipo', 'descricao', 'valor', 'data', 'quilometragem',
                  'fornecedor', 'forma_pagamento', 'comprovante']
        widgets = {
            'data': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'descricao': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Combustivel entra somente via Abastecimento (evita contagem dupla).
        self.fields['tipo'].choices = Custo.TIPO_CHOICES_MANUAL

    def clean_valor(self):
        valor = self.cleaned_data['valor']
        if valor is not None and valor <= 0:
            raise forms.ValidationError('O valor deve ser maior que zero.')
        return valor


class AbastecimentoForm(forms.ModelForm):
    class Meta:
        model = Abastecimento
        fields = ['data', 'quilometragem', 'litros', 'valor_total',
                  'tipo_combustivel', 'posto']
        widgets = {'data': _DATE}

    def clean_litros(self):
        litros = self.cleaned_data['litros']
        if litros is not None and litros <= 0:
            raise forms.ValidationError('Os litros devem ser maiores que zero.')
        return litros

    def clean_valor_total(self):
        valor = self.cleaned_data['valor_total']
        if valor is not None and valor <= 0:
            raise forms.ValidationError('O valor deve ser maior que zero.')
        return valor


class RegistroQuilometragemForm(forms.ModelForm):
    class Meta:
        model = RegistroQuilometragem
        fields = ['data', 'quilometragem', 'origem', 'observacao']
        widgets = {'data': _DATE, 'observacao': forms.Textarea(attrs={'rows': 2})}


class PlanoManutencaoForm(forms.ModelForm):
    class Meta:
        model = PlanoManutencao
        fields = ['descricao', 'intervalo_km', 'intervalo_dias',
                  'km_referencia', 'data_referencia']
        widgets = {'data_referencia': _DATE}

    def clean(self):
        dados = super().clean()
        if not dados.get('intervalo_km') and not dados.get('intervalo_dias'):
            raise forms.ValidationError(
                'Informe ao menos um intervalo: por km ou por dias.'
            )
        return dados
