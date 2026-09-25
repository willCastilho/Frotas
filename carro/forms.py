from django import forms

from carro.models import (
    Abastecimento,
    AtribuicaoVeiculo,
    Custo,
    Documento,
    Motorista,
    PlanoManutencao,
    RegistroQuilometragem,
    Solicitante,
    SolicitacaoVeiculo,
    Veiculo,
)

_DATE = forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d')
_DATETIME = forms.DateTimeInput(
    attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M')


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
        fields = ['tipo', 'vencimento', 'valor', 'observacao']
        widgets = {'vencimento': _DATE}
        labels = {'valor': 'Valor da taxa (R$)'}
        help_texts = {
            'valor': 'Opcional. Se informado, entra como custo do veículo.'
        }


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


class EscalaMontarForm(forms.Form):
    """Monta a escala de um motorista em um veiculo por um periodo (o sistema
    cria a escala de cada dia do intervalo)."""
    motorista = forms.ModelChoiceField(
        queryset=Motorista.objects.none(), label='Motorista')
    veiculo = forms.ModelChoiceField(
        queryset=Veiculo.objects.none(), label='Veículo')
    data_inicio = forms.DateField(widget=_DATE, label='De')
    data_fim = forms.DateField(widget=_DATE, label='Até')
    somente_dias_uteis = forms.BooleanField(
        required=False, initial=True, label='Somente dias úteis (seg–sex)')
    destino = forms.CharField(max_length=200, required=False, label='Destino')
    observacao = forms.CharField(max_length=200, required=False, label='Observação')

    def __init__(self, *args, organizacao=None, **kwargs):
        super().__init__(*args, **kwargs)
        if organizacao is not None:
            self.fields['motorista'].queryset = Motorista.objects.filter(
                organizacao=organizacao, status='ativo')
            self.fields['veiculo'].queryset = Veiculo.objects.filter(
                organizacao=organizacao, status='ativo')

    def clean(self):
        dados = super().clean()
        inicio, fim = dados.get('data_inicio'), dados.get('data_fim')
        if inicio and fim:
            if fim < inicio:
                self.add_error('data_fim', 'A data final não pode ser anterior à inicial.')
            elif (fim - inicio).days > 366:
                self.add_error('data_fim', 'O período não pode passar de 1 ano.')
        return dados


class SolicitanteSignupForm(forms.Form):
    """Auto-cadastro do solicitante: cria login + cadastro (status pendente)."""
    username = forms.CharField(max_length=150, label='Usuário (login)')
    nome = forms.CharField(max_length=120, label='Nome completo')
    email = forms.EmailField(label='E-mail')
    cargo = forms.CharField(max_length=120, required=False, label='Cargo')
    setor = forms.CharField(max_length=120, label='Setor')
    telefone = forms.CharField(max_length=20, required=False, label='Telefone')
    cpf = forms.CharField(max_length=14, required=False, label='CPF')
    cnh = forms.CharField(max_length=20, required=False, label='Número da CNH')
    cnh_categoria = forms.ChoiceField(
        choices=[('', '---')] + list(Motorista.CNH_CATEGORIAS),
        required=False, label='Categoria da CNH')
    cnh_validade = forms.DateField(
        required=False, widget=_DATE, label='Validade da CNH')
    password1 = forms.CharField(widget=forms.PasswordInput, label='Senha')
    password2 = forms.CharField(
        widget=forms.PasswordInput, label='Confirme a senha')

    def clean_username(self):
        from django.contrib.auth.models import User
        username = self.cleaned_data['username']
        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError('Este usuário já existe.')
        return username

    def clean(self):
        dados = super().clean()
        if dados.get('password1') != dados.get('password2'):
            self.add_error('password2', 'As senhas não conferem.')
        return dados


class SolicitacaoForm(forms.ModelForm):
    """Pedido de veiculo feito pelo solicitante."""
    class Meta:
        model = SolicitacaoVeiculo
        fields = ['setor', 'saida_prevista', 'retorno_previsto', 'destino',
                  'precisa_motorista', 'justificativa']
        widgets = {
            'saida_prevista': _DATETIME,
            'retorno_previsto': _DATETIME,
            'justificativa': forms.Textarea(attrs={'rows': 3}),
        }
        labels = {
            'saida_prevista': 'Saída prevista',
            'retorno_previsto': 'Retorno previsto',
            'precisa_motorista': 'Preciso de um motorista designado',
        }

    def clean(self):
        dados = super().clean()
        saida = dados.get('saida_prevista')
        retorno = dados.get('retorno_previsto')
        if saida and retorno and retorno <= saida:
            self.add_error('retorno_previsto', 'O retorno deve ser depois da saída.')
        return dados


class AprovarSolicitacaoForm(forms.Form):
    """Aprovacao do gestor: escolhe um veiculo livre (e motorista, se preciso)."""
    veiculo = forms.ModelChoiceField(
        queryset=Veiculo.objects.none(), label='Veículo disponível')
    motorista = forms.ModelChoiceField(
        queryset=Motorista.objects.none(), required=False,
        label='Motorista (se necessário)')

    def __init__(self, *args, veiculos=None, motoristas=None,
                 precisa_motorista=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['veiculo'].queryset = veiculos if veiculos is not None \
            else Veiculo.objects.none()
        self.fields['motorista'].queryset = motoristas if motoristas is not None \
            else Motorista.objects.none()
        self.precisa_motorista = precisa_motorista
        if precisa_motorista:
            self.fields['motorista'].required = True

    def clean_motorista(self):
        motorista = self.cleaned_data.get('motorista')
        if self.precisa_motorista and not motorista:
            raise forms.ValidationError(
                'Esta solicitação pediu motorista; selecione um disponível.')
        return motorista


class RetiradaForm(forms.Form):
    """Retirada do veiculo pelo solicitante: hora e KM de saida."""
    saida_real = forms.DateTimeField(
        widget=_DATETIME, label='Saída real (data e hora)')
    km_inicial = forms.IntegerField(min_value=0, label='KM de saída do veículo')

    def __init__(self, *args, km_minimo=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.km_minimo = km_minimo
        if km_minimo:
            self.fields['km_inicial'].help_text = (
                f'O odômetro atual do veículo é {km_minimo} km.')

    def clean_km_inicial(self):
        km = self.cleaned_data['km_inicial']
        if self.km_minimo and km < self.km_minimo:
            raise forms.ValidationError(
                f'O KM de saída não pode ser menor que o odômetro atual '
                f'({self.km_minimo} km).')
        return km


class DevolucaoForm(forms.Form):
    """Devolucao do veiculo pelo solicitante: hora real e KM final (que
    alimenta o odometro)."""
    retorno_real = forms.DateTimeField(
        widget=_DATETIME, label='Retorno real (data e hora)')
    km_final = forms.IntegerField(min_value=0, label='KM final do veículo')
    obs_devolucao = forms.CharField(
        required=False, widget=forms.Textarea(attrs={'rows': 3}),
        label='Observações / ocorrências')

    def __init__(self, *args, km_minimo=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.km_minimo = km_minimo
        if km_minimo:
            self.fields['km_final'].help_text = (
                f'O odômetro atual do veículo é {km_minimo} km.')

    def clean_km_final(self):
        km = self.cleaned_data['km_final']
        if self.km_minimo and km < self.km_minimo:
            raise forms.ValidationError(
                f'O KM final não pode ser menor que o odômetro atual '
                f'({self.km_minimo} km).')
        return km
