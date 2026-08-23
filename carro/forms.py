from django import forms

from carro.models import (
    Abastecimento,
    AtribuicaoVeiculo,
    Custo,
    Documento,
    Motorista,
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
    RECORRENCIA_CHOICES = [
        ('nenhuma', 'Lançamento único'),
        ('parcelado', 'Parcelado (dividir o valor)'),
        ('mensal', 'Repetir todo mês (mesmo valor)'),
        ('anual', 'Repetir todo ano (mesmo valor)'),
    ]

    recorrencia = forms.ChoiceField(
        choices=RECORRENCIA_CHOICES, required=False, initial='nenhuma',
        label='Recorrência',
        help_text='Para IPVA, seguro e licenciamento parcelados ou recorrentes.')
    ocorrencias = forms.IntegerField(
        required=False, min_value=1, max_value=60, initial=1,
        label='Nº de parcelas/repetições',
        help_text='Quantos lançamentos gerar (ex.: 12 para IPVA em 12x).')

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
        # Recorrencia so faz sentido ao criar; ao editar um lancamento existente
        # nao reprocessamos a serie.
        if self.instance and self.instance.pk:
            self.fields.pop('recorrencia', None)
            self.fields.pop('ocorrencias', None)

    def clean_valor(self):
        valor = self.cleaned_data['valor']
        if valor is not None and valor <= 0:
            raise forms.ValidationError('O valor deve ser maior que zero.')
        return valor

    def clean(self):
        dados = super().clean()
        recorrencia = dados.get('recorrencia') or 'nenhuma'
        ocorrencias = dados.get('ocorrencias') or 1
        if recorrencia != 'nenhuma' and ocorrencias < 2:
            self.add_error(
                'ocorrencias',
                'Para recorrência ou parcelamento, informe 2 ou mais.')
        return dados


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


class DocumentoForm(forms.ModelForm):
    class Meta:
        model = Documento
        fields = ['tipo', 'vencimento', 'observacao']
        widgets = {'vencimento': _DATE}


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


class MotoristaForm(forms.ModelForm):
    class Meta:
        model = Motorista
        fields = ['nome', 'cpf', 'cnh', 'cnh_categoria', 'cnh_validade',
                  'telefone', 'email', 'status', 'observacoes']
        widgets = {
            'cnh_validade': _DATE,
            'observacoes': forms.Textarea(attrs={'rows': 3}),
        }


class AtribuicaoVeiculoForm(forms.ModelForm):
    """Vincula um motorista a um veiculo. As opcoes de veiculo e motorista sao
    limitadas a organizacao do usuario."""
    class Meta:
        model = AtribuicaoVeiculo
        fields = ['motorista', 'veiculo', 'data_inicio', 'data_fim', 'observacao']
        widgets = {'data_inicio': _DATE, 'data_fim': _DATE}

    def __init__(self, *args, organizacao=None, **kwargs):
        super().__init__(*args, **kwargs)
        if organizacao is not None:
            self.fields['motorista'].queryset = Motorista.objects.filter(
                organizacao=organizacao, status='ativo')
            self.fields['veiculo'].queryset = Veiculo.objects.filter(
                organizacao=organizacao)

    def clean(self):
        dados = super().clean()
        inicio, fim = dados.get('data_inicio'), dados.get('data_fim')
        if inicio and fim and fim < inicio:
            self.add_error('data_fim', 'A data de fim não pode ser anterior ao início.')
        return dados
