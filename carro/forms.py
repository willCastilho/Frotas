from django import forms

from carro.models import Custo, Veiculo


class VeiculoForm(forms.ModelForm):
    class Meta:
        model = Veiculo
        fields = ['marca', 'modelo', 'ano', 'cor', 'data_compra', 'status', 'picture']
        widgets = {
            'data_compra': forms.DateInput(
                attrs={'type': 'date'}, format='%Y-%m-%d'
            ),
        }

    def clean_ano(self):
        ano = self.cleaned_data['ano']
        if ano < 1900 or ano > 2100:
            raise forms.ValidationError('Informe um ano entre 1900 e 2100.')
        return ano


class CustoForm(forms.ModelForm):
    class Meta:
        model = Custo
        fields = ['tipo', 'descricao', 'valor', 'data']
        widgets = {
            'data': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'descricao': forms.Textarea(attrs={'rows': 4}),
        }

    def clean_valor(self):
        valor = self.cleaned_data['valor']
        if valor is not None and valor <= 0:
            raise forms.ValidationError('O valor deve ser maior que zero.')
        return valor
