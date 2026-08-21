from django.test import TestCase
from django.urls import reverse
from django.contrib.auth.models import User

from datetime import date, timedelta

from carro.forms import CustoForm, VeiculoForm
from carro.models import (
    Abastecimento,
    Custo,
    PlanoManutencao,
    RegistroQuilometragem,
    Veiculo,
)


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
            'tipo': 'manutencao', 'descricao': 'Troca de pneu',
            'valor': '150.00', 'data': '2024-01-10',
        })
        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(Custo.objects.count(), 1)
        self.assertEqual(Custo.objects.first().veiculo, veiculo)


class MetricasFrotaTests(TestCase):
    def setUp(self):
        self.veiculo = cria_veiculo()

    def test_km_atual_pega_maior_leitura(self):
        Abastecimento.objects.create(
            veiculo=self.veiculo, quilometragem=1000, litros=30,
            valor_total=180, data='2024-01-01')
        RegistroQuilometragem.objects.create(
            veiculo=self.veiculo, quilometragem=1500, data='2024-02-01')
        self.assertEqual(self.veiculo.km_atual(), 1500)

    def test_consumo_medio_tanque_cheio(self):
        # 1000 -> 1400 km = 400 km; litros apos o primeiro = 40 -> 10 km/l
        Abastecimento.objects.create(
            veiculo=self.veiculo, quilometragem=1000, litros=40,
            valor_total=240, data='2024-01-01')
        Abastecimento.objects.create(
            veiculo=self.veiculo, quilometragem=1400, litros=40,
            valor_total=240, data='2024-01-10')
        self.assertAlmostEqual(self.veiculo.consumo_medio(), 10.0)

    def test_consumo_medio_insuficiente(self):
        self.assertIsNone(self.veiculo.consumo_medio())

    def test_custo_por_km(self):
        Custo.objects.create(veiculo=self.veiculo, tipo='outro',
                             descricao='x', valor=1000, data='2024-01-01')
        # O abastecimento gera automaticamente um custo de combustivel (180).
        Abastecimento.objects.create(
            veiculo=self.veiculo, quilometragem=1000, litros=30,
            valor_total=180, data='2024-01-01')
        RegistroQuilometragem.objects.create(
            veiculo=self.veiculo, quilometragem=3000, data='2024-02-01')
        # (1000 + 180) de custo / 2000 km = 0.59 R$/km
        self.assertAlmostEqual(self.veiculo.custo_por_km(), 1180 / 2000)


class PlanoManutencaoTests(TestCase):
    def setUp(self):
        self.veiculo = cria_veiculo()

    def test_status_atrasado_por_km(self):
        plano = PlanoManutencao.objects.create(
            veiculo=self.veiculo, descricao='Óleo',
            intervalo_km=10000, km_referencia=70000)
        # proxima_km = 80000; km_atual 82000 -> atrasado
        self.assertEqual(plano.status(82000)['cor'], 'red')

    def test_status_em_dia_por_km(self):
        plano = PlanoManutencao.objects.create(
            veiculo=self.veiculo, descricao='Óleo',
            intervalo_km=10000, km_referencia=70000)
        self.assertEqual(plano.status(72000)['cor'], 'green')

    def test_status_vencida_por_data(self):
        plano = PlanoManutencao.objects.create(
            veiculo=self.veiculo, descricao='Licenciamento',
            intervalo_dias=30, data_referencia=date.today() - timedelta(days=60))
        self.assertEqual(plano.status()['cor'], 'red')


class FrotaViewsTests(LogadoMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.veiculo = cria_veiculo()

    def test_novo_abastecimento(self):
        url = reverse('novo_abastecimento', args=[self.veiculo.id])
        resposta = self.client.post(url, {
            'data': '2024-01-01', 'quilometragem': 1000, 'litros': '30.000',
            'valor_total': '180.00', 'tipo_combustivel': 'gasolina', 'posto': 'Shell',
        })
        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(Abastecimento.objects.count(), 1)

    def test_plano_exige_algum_intervalo(self):
        url = reverse('novo_plano_manutencao', args=[self.veiculo.id])
        resposta = self.client.post(url, {'descricao': 'Sem intervalo'})
        self.assertEqual(resposta.status_code, 200)  # form invalido, re-render
        self.assertEqual(PlanoManutencao.objects.count(), 0)

    def test_detalhes_renderiza_com_dominio(self):
        Abastecimento.objects.create(
            veiculo=self.veiculo, quilometragem=1000, litros=30,
            valor_total=180, data='2024-01-01')
        resposta = self.client.get(reverse('detalhes_veiculo', args=[self.veiculo.id]))
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, 'Consumo médio')


class CombustivelFonteUnicaTests(LogadoMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.veiculo = cria_veiculo()

    def test_abastecimento_gera_custo(self):
        ab = Abastecimento.objects.create(
            veiculo=self.veiculo, quilometragem=1000, litros=30,
            valor_total=180, data='2024-01-01')
        self.assertIsNotNone(ab.custo)
        self.assertEqual(ab.custo.tipo, 'combustivel')
        self.assertEqual(float(ab.custo.valor), 180.0)
        self.assertEqual(Custo.objects.filter(tipo='combustivel').count(), 1)

    def test_excluir_abastecimento_remove_custo(self):
        ab = Abastecimento.objects.create(
            veiculo=self.veiculo, quilometragem=1000, litros=30,
            valor_total=180, data='2024-01-01')
        ab.delete()
        self.assertEqual(Custo.objects.filter(tipo='combustivel').count(), 0)

    def test_form_custo_nao_oferece_combustivel(self):
        from carro.forms import CustoForm
        tipos = [c[0] for c in CustoForm().fields['tipo'].choices]
        self.assertNotIn('combustivel', tipos)

    def test_custo_de_abastecimento_nao_edita_direto(self):
        ab = Abastecimento.objects.create(
            veiculo=self.veiculo, quilometragem=1000, litros=30,
            valor_total=180, data='2024-01-01')
        r = self.client.get(reverse('editar_custo', args=[ab.custo.id]))
        self.assertEqual(r.status_code, 302)


class MetaCustoTests(TestCase):
    def test_custo_vs_meta(self):
        v = cria_veiculo(meta_custo_mensal=1000)
        hoje = date.today().replace(day=10)
        Custo.objects.create(veiculo=v, tipo='outro', descricao='x',
                             valor=1200, data=hoje)
        info = v.custo_vs_meta()
        self.assertEqual(info['pct'], 120)
        self.assertEqual(info['cor'], 'red')
        self.assertEqual(info['pct_barra'], 100)

    def test_sem_meta_retorna_none(self):
        v = cria_veiculo()
        self.assertIsNone(v.custo_vs_meta())


class DashboardTests(LogadoMixin, TestCase):
    def test_dashboard_renderiza(self):
        cria_veiculo()
        resposta = self.client.get(reverse('dashboard'))
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, 'Painel de Gestão')

    def test_relatorios_renderiza(self):
        resposta = self.client.get(reverse('relatorios'))
        self.assertEqual(resposta.status_code, 200)

    def test_exportar_csv(self):
        veiculo = cria_veiculo()
        Custo.objects.create(veiculo=veiculo, tipo='combustivel',
                             descricao='Gasolina', valor=100, data='2024-01-01')
        resposta = self.client.get(reverse('exportar_custos'), {'formato': 'csv'})
        self.assertEqual(resposta.status_code, 200)
        self.assertIn('text/csv', resposta['Content-Type'])
        self.assertIn('Gasolina', resposta.content.decode('utf-8'))

    def test_exportar_xlsx(self):
        veiculo = cria_veiculo()
        Custo.objects.create(veiculo=veiculo, tipo='combustivel',
                             descricao='Gasolina', valor=100, data='2024-01-01')
        resposta = self.client.get(reverse('exportar_custos'), {'formato': 'xlsx'})
        self.assertEqual(resposta.status_code, 200)
        self.assertIn('spreadsheetml', resposta['Content-Type'])


class GruposTests(TestCase):
    def test_criar_grupos(self):
        from django.contrib.auth.models import Group
        from django.core.management import call_command

        call_command('criar_grupos')
        nomes = set(Group.objects.values_list('name', flat=True))
        self.assertEqual(
            nomes, {'Administrador', 'Gestor', 'Operador', 'Consulta'})
        # Consulta so tem permissoes de visualizacao
        consulta = Group.objects.get(name='Consulta')
        for perm in consulta.permissions.all():
            self.assertTrue(perm.codename.startswith('view_'))


class AuditoriaTests(TestCase):
    def test_alteracao_gera_log(self):
        from auditlog.models import LogEntry

        veiculo = cria_veiculo()
        self.assertTrue(
            LogEntry.objects.get_for_object(veiculo).exists()
        )


class CriarAdminTests(TestCase):
    def test_cria_e_e_idempotente(self):
        import os
        from django.contrib.auth import get_user_model
        from django.core.management import call_command

        User = get_user_model()
        env = {
            'DJANGO_SUPERUSER_USERNAME': 'admin',
            'DJANGO_SUPERUSER_PASSWORD': 'senhaForte123',
            'DJANGO_SUPERUSER_EMAIL': 'admin@exemplo.com',
        }
        antigo = {k: os.environ.get(k) for k in env}
        os.environ.update(env)
        try:
            call_command('criar_admin')
            self.assertTrue(User.objects.filter(username='admin', is_superuser=True).exists())
            # Rodar de novo nao deve duplicar nem falhar
            call_command('criar_admin')
            self.assertEqual(User.objects.filter(username='admin').count(), 1)
        finally:
            for k, v in antigo.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v

    def test_sem_variaveis_nao_cria(self):
        from django.contrib.auth import get_user_model
        from django.core.management import call_command

        User = get_user_model()
        call_command('criar_admin')
        self.assertEqual(User.objects.filter(is_superuser=True).count(), 0)
