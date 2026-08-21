from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from contas.models import Organizacao, PerfilUsuario


class SignupForm(UserCreationForm):
    email = forms.EmailField(required=True, label='E-mail')
    nome_organizacao = forms.CharField(
        max_length=120, label='Nome da empresa / organização')
    aceite_lgpd = forms.BooleanField(
        required=True,
        label='Li e aceito os Termos de Uso e a Política de Privacidade',
    )

    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2']

    def clean_email(self):
        email = self.cleaned_data['email']
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('Já existe uma conta com este e-mail.')
        return email


class CriarOrganizacaoForm(forms.ModelForm):
    class Meta:
        model = Organizacao
        fields = ['nome']
        labels = {'nome': 'Nome da empresa / organização'}


class ConvidarUsuarioForm(forms.Form):
    username = forms.CharField(max_length=150, label='Usuário')
    email = forms.EmailField(label='E-mail')
    papel = forms.ChoiceField(choices=PerfilUsuario.PAPEL_CHOICES, label='Papel')

    def clean_username(self):
        username = self.cleaned_data['username']
        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError('Este nome de usuário já existe.')
        return username


class PapelForm(forms.Form):
    papel = forms.ChoiceField(choices=PerfilUsuario.PAPEL_CHOICES, label='Papel')
