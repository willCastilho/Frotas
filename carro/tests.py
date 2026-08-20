from django.test import TestCase
from django.urls import reverse
from django.contrib.auth.models import User

from carro.forms import CustoForm, VeiculoForm
from carro.models import Custo, Veiculo


def cria_veiculo(**kwargs):
    dados = dict(
        modelo='Vectra', marca='Chevrolet', ano=2010, cor='Prata',
        data_compra='2020-01-01', status='ativo',
    )
    dados.update(kwargs)
    return Veiculo.objects.create(**dados)


class AutenticacaoTests(TestCase):
    def test_home_exige_login(self):
        """Home sem login redireciona para a tela de login."""
        resposta = self.client.get(reverse('home'))
        self.assertEqual(resposta.status_code, 302)
        self.assertIn(reverse('login'), resposta.url)

    def test_pagina_login_renderiza(self):
        resposta = self.client.get(reverse('login'))
        self.assertEqual(resposta.status_code, 200)


class LogadoMixin:
    def setUp(self):
        User.objects.create_user('teste', password='senha12345')
        self.client.login(username='teste', password='senha12345')


class HomeTests(LogadoMixin, TestCase):
    def test_home_com_banco_vazio(self):
        """Regressao: com nenhum veiculo, a home deve responder 200 (o
        'context' nao pode estar preso dentro do for)."""
        resposta = self.client.get(reverse('home'))
        self.assertEqual(resposta.status_code, 200)

    def test_home_com_veiculo(self):
        cria_veiculo()
        resposta = self.client.get(reverse('home'))
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, 'Vectra')

    def test_home_pagina(self):
        for i in range(12):
            cria_veiculo(modelo=f'Carro {i}')
        resposta = self.client.get(reverse('home'))
        # 9 por pagina -> 2 paginas
        self.assertEqual(resposta.context['page_obj'].paginator.num_pages, 2)


class ExclusaoTests(LogadoMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.veiculo = cria_veiculo()

    def test_excluir_veiculo_via_get_bloqueado(self):
        """Exclusao nunca deve acontecer por GET (require_POST)."""
        url = reverse('excluir_veiculo', args=[self.veiculo.id])
        resposta = self.client.get(url)
        self.assertEqual(resposta.status_code, 405)
        self.assertEqual(Veiculo.objects.count(), 1)

    def test_excluir_veiculo_via_post(self):
        url = reverse('excluir_veiculo', args=[self.veiculo.id])
        resposta = self.client.post(url)
        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(Veiculo.objects.count(), 0)


class FormsTests(TestCase):
    def test_veiculo_ano_invalido(self):
        form = VeiculoForm(data={
            'marca': 'Fiat', 'modelo': 'Uno', 'ano': 1800, 'cor': 'Branco',
            'data_compra': '2020-01-01', 'status': 'ativo',
        })
        self.assertFalse(form.is_valid())
        self.assertIn('ano', form.errors)

    def test_veiculo_valido(self):
        form = VeiculoForm(data={
            'marca': 'Fiat', 'modelo': 'Uno', 'ano': 2015, 'cor': 'Branco',
            'data_compra': '2020-01-01', 'status': 'ativo',
        })
        self.assertTrue(form.is_valid())

    def test_custo_valor_negativo(self):
        form = CustoForm(data={
            'tipo': 'combustivel', 'descricao': 'Gasolina',
            'valor': '-50.00', 'data': '2024-01-01',
        })
        self.assertFalse(form.is_valid())
        self.assertIn('valor', form.errors)


class CustoFluxoTests(LogadoMixin, TestCase):
    def test_novo_custo_associa_veiculo(self):
        veiculo = cria_veiculo()
        url = reverse('novo_custo', args=[veiculo.id])
        resposta = self.client.post(url, {
            'tipo': 'combustivel', 'descricao': 'Gasolina',
            'valor': '150.00', 'data': '2024-01-10',
        })
        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(Custo.objects.count(), 1)
        self.assertEqual(Custo.objects.first().veiculo, veiculo)
