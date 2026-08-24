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
    papel = forms.ChoiceField(
        choices=PerfilUsuario.PAPEIS_DA_ORGANIZACAO, label='Papel')
    motorista = forms.ModelChoiceField(
        queryset=None, required=False, label='Motorista vinculado',
        help_text='Obrigatório para operador: liga este login a um motorista.')

    def __init__(self, *args, organizacao=None, incluir_admin=False, **kwargs):
        super().__init__(*args, **kwargs)
        # O admin global pode criar qualquer papel (incl. administrador).
        if incluir_admin:
            self.fields['papel'].choices = PerfilUsuario.PAPEL_CHOICES
        from carro.models import Motorista
        qs = Motorista.objects.none()
        if organizacao is not None:
            qs = Motorista.objects.filter(organizacao=organizacao, user__isnull=True)
        self.fields['motorista'].queryset = qs

    def clean_username(self):
        username = self.cleaned_data['username']
        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError('Este nome de usuário já existe.')
        return username

    def clean(self):
        dados = super().clean()
        if dados.get('papel') == PerfilUsuario.PAPEL_OPERADOR and not dados.get('motorista'):
            self.add_error(
                'motorista',
                'Selecione o motorista que este operador representa.')
        return dados


class OrganizacaoAdminForm(forms.ModelForm):
    class Meta:
        model = Organizacao
        fields = ['nome', 'plano', 'assinatura_ativa', 'assinatura_valida_ate']
        widgets = {
            'assinatura_valida_ate': forms.DateInput(
                attrs={'type': 'date'}, format='%Y-%m-%d'),
        }


class PapelAdminForm(forms.Form):
    """Alteracao de papel/estado pelo admin global (inclui administrador)."""
    papel = forms.ChoiceField(choices=PerfilUsuario.PAPEL_CHOICES, label='Papel')
    ativo = forms.BooleanField(required=False, initial=True, label='Usuário ativo')


class PapelForm(forms.Form):
    papel = forms.ChoiceField(
        choices=PerfilUsuario.PAPEIS_DA_ORGANIZACAO, label='Papel')
