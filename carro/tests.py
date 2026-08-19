from django.test import TestCase
from django.urls import reverse
from django.contrib.auth.models import User

from carro.models import Veiculo


class AutenticacaoTests(TestCase):
    def test_home_exige_login(self):
        """Home sem login redireciona para a tela de login."""
        resposta = self.client.get(reverse('home'))
        self.assertEqual(resposta.status_code, 302)
        self.assertIn(reverse('login'), resposta.url)

    def test_pagina_login_renderiza(self):
        resposta = self.client.get(reverse('login'))
        self.assertEqual(resposta.status_code, 200)


class HomeTests(TestCase):
    def setUp(self):
        User.objects.create_user('teste', password='senha12345')
        self.client.login(username='teste', password='senha12345')

    def test_home_com_banco_vazio(self):
        """Regressao: com nenhum veiculo, a home deve responder 200 (o
        'context' nao pode estar preso dentro do for)."""
        resposta = self.client.get(reverse('home'))
        self.assertEqual(resposta.status_code, 200)

    def test_home_com_veiculo(self):
        Veiculo.objects.create(
            modelo='Vectra', marca='Chevrolet', ano=2010, cor='Prata',
            Data_compra='2020-01-01', status='ativo',
        )
        resposta = self.client.get(reverse('home'))
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, 'Vectra')


class ExclusaoTests(TestCase):
    def setUp(self):
        User.objects.create_user('teste', password='senha12345')
        self.client.login(username='teste', password='senha12345')
        self.veiculo = Veiculo.objects.create(
            modelo='Vectra', marca='Chevrolet', ano=2010, cor='Prata',
            Data_compra='2020-01-01', status='ativo',
        )

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
