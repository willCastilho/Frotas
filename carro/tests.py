from datetime import date, timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from carro.forms import CustoForm, VeiculoForm
from carro.models import (
    Abastecimento,
    Custo,
    PlanoManutencao,
    RegistroQuilometragem,
    Veiculo,
)
from contas.models import Organizacao, PerfilUsuario, Plano


def cria_org(nome='Org Teste', limite_veiculos=0):
    plano = Plano.objects.create(
        nome='Plano', slug=f'plano-{Plano.objects.count()}',
        limite_veiculos=limite_veiculos)
    return Organizacao.objects.create(nome=nome, plano=plano)


def cria_veiculo(org=None, **kwargs):
    if org is None:
        org = cria_org(nome=f'Org {Veiculo.objects.count()}')
    dados = dict(
        modelo='Vectra', marca='Chevrolet', ano=2010, cor='Prata',
        data_compra='2020-01-01', status='ativo',
    )
    dados.update(kwargs)
    return Veiculo.objects.create(organizacao=org, **dados)


class LogadoMixin:
    papel = PerfilUsuario.PAPEL_ADMIN

    def setUp(self):
        self.org = cria_org('Org do Teste')
        self.user = User.objects.create_user(
            'teste', password='senha12345', email='teste@ex.com')
        PerfilUsuario.objects.create(
            user=self.user, organizacao=self.org, papel=self.papel)
        self.client.login(username='teste', password='senha12345')

    def cria_veiculo(self, **kwargs):
        return cria_veiculo(org=self.org, **kwargs)


class AutenticacaoTests(TestCase):
    def test_home_exige_login(self):
        resposta = self.client.get(reverse('home'))
        self.assertEqual(resposta.status_code, 302)
        self.assertIn(reverse('login'), resposta.url)

    def test_pagina_login_renderiza(self):
        self.assertEqual(self.client.get(reverse('login')).status_code, 200)


class HomeTests(LogadoMixin, TestCase):
    def test_home_com_banco_vazio(self):
        self.assertEqual(self.client.get(reverse('home')).status_code, 200)

    def test_home_com_veiculo(self):
        self.cria_veiculo()
        resposta = self.client.get(reverse('home'))
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, 'Vectra')

    def test_home_pagina(self):
        for i in range(12):
            self.cria_veiculo(modelo=f'Carro {i}')
        resposta = self.client.get(reverse('home'))
        self.assertEqual(resposta.context['page_obj'].paginator.num_pages, 2)


class IsolamentoTests(TestCase):
    """Garante o isolamento multi-tenant: uma organizacao nao ve dados de outra."""
    def setUp(self):
        self.org_a = cria_org('A')
        self.veiculo_a = cria_veiculo(org=self.org_a, modelo='CarroA')
        self.org_b = cria_org('B')
        self.user_b = User.objects.create_user('userb', password='senha12345')
        PerfilUsuario.objects.create(
            user=self.user_b, organizacao=self.org_b, papel='admin')
        self.client.login(username='userb', password='senha12345')

    def test_nao_ve_veiculo_de_outra_org(self):
        resposta = self.client.get(reverse('home'))
        self.assertNotContains(resposta, 'CarroA')

    def test_detalhe_de_outra_org_da_404(self):
        r = self.client.get(reverse('detalhes_veiculo', args=[self.veiculo_a.id]))
        self.assertEqual(r.status_code, 404)

    def test_excluir_de_outra_org_da_404(self):
        r = self.client.post(reverse('excluir_veiculo', args=[self.veiculo_a.id]))
        self.assertEqual(r.status_code, 404)
        self.assertEqual(Veiculo.objects.filter(id=self.veiculo_a.id).count(), 1)


class CadastroOnboardingTests(TestCase):
    def test_signup_cria_org_e_perfil(self):
        resposta = self.client.post(reverse('cadastro'), {
            'username': 'novoemp', 'email': 'novo@ex.com',
            'password1': 'SenhaForte!123', 'password2': 'SenhaForte!123',
            'nome_organizacao': 'Empresa X', 'aceite_lgpd': 'on',
        })
        self.assertEqual(resposta.status_code, 302)
        user = User.objects.get(username='novoemp')
        self.assertTrue(hasattr(user, 'perfil'))
        self.assertEqual(user.perfil.organizacao.nome, 'Empresa X')
        self.assertEqual(user.perfil.papel, 'admin')

    def test_usuario_sem_org_vai_para_onboarding(self):
        User.objects.create_user('semorg', password='senha12345')
        self.client.login(username='semorg', password='senha12345')
        r = self.client.get(reverse('home'))
        self.assertEqual(r.status_code, 302)
        self.assertIn(reverse('criar_organizacao'), r.url)


class RBACTests(LogadoMixin, TestCase):
    papel = PerfilUsuario.PAPEL_CONSULTA

    def test_consulta_nao_cria_veiculo(self):
        r = self.client.post(reverse('novo_veiculo'), {
            'marca': 'Fiat', 'modelo': 'Uno', 'ano': 2015, 'cor': 'Branco',
            'data_compra': '2020-01-01', 'status': 'ativo',
        })
        self.assertEqual(r.status_code, 302)
        self.assertEqual(Veiculo.objects.count(), 0)

    def test_consulta_ve_a_home(self):
        self.assertEqual(self.client.get(reverse('home')).status_code, 200)


class LimitePlanoTests(LogadoMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.org.plano.limite_veiculos = 1
        self.org.plano.save()

    def test_bloqueia_acima_do_limite(self):
        self.cria_veiculo()  # 1 veiculo = no limite
        r = self.client.post(reverse('novo_veiculo'), {
            'marca': 'Fiat', 'modelo': 'Uno', 'ano': 2015, 'cor': 'Branco',
            'data_compra': '2020-01-01', 'status': 'ativo',
        })
        self.assertEqual(r.status_code, 302)
        self.assertEqual(Veiculo.objects.count(), 1)


class ExclusaoTests(LogadoMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.veiculo = self.cria_veiculo()

    def test_excluir_veiculo_via_get_bloqueado(self):
        r = self.client.get(reverse('excluir_veiculo', args=[self.veiculo.id]))
        self.assertEqual(r.status_code, 405)
        self.assertEqual(Veiculo.objects.count(), 1)

    def test_excluir_veiculo_via_post(self):
        r = self.client.post(reverse('excluir_veiculo', args=[self.veiculo.id]))
        self.assertEqual(r.status_code, 302)
        self.assertEqual(Veiculo.objects.count(), 0)


class FormsTests(TestCase):
    def test_veiculo_ano_invalido(self):
        form = VeiculoForm(data={
            'marca': 'Fiat', 'modelo': 'Uno', 'ano': 1800, 'cor': 'Branco',
            'data_compra': '2020-01-01', 'status': 'ativo'})
        self.assertFalse(form.is_valid())
        self.assertIn('ano', form.errors)

    def test_veiculo_valido(self):
        form = VeiculoForm(data={
            'marca': 'Fiat', 'modelo': 'Uno', 'ano': 2015, 'cor': 'Branco',
            'data_compra': '2020-01-01', 'status': 'ativo'})
        self.assertTrue(form.is_valid())

    def test_custo_valor_negativo(self):
        form = CustoForm(data={
            'tipo': 'manutencao', 'descricao': 'x',
            'valor': '-50.00', 'data': '2024-01-01'})
        self.assertFalse(form.is_valid())
        self.assertIn('valor', form.errors)


class CustoFluxoTests(LogadoMixin, TestCase):
    def test_novo_custo_associa_veiculo(self):
        veiculo = self.cria_veiculo()
        r = self.client.post(reverse('novo_custo', args=[veiculo.id]), {
            'tipo': 'manutencao', 'descricao': 'Troca de pneu',
            'valor': '150.00', 'data': '2024-01-10'})
        self.assertEqual(r.status_code, 302)
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
        Abastecimento.objects.create(
            veiculo=self.veiculo, quilometragem=1000, litros=30,
            valor_total=180, data='2024-01-01')
        RegistroQuilometragem.objects.create(
            veiculo=self.veiculo, quilometragem=3000, data='2024-02-01')
        self.assertAlmostEqual(self.veiculo.custo_por_km(), 1180 / 2000)


class PlanoManutencaoTests(TestCase):
    def setUp(self):
        self.veiculo = cria_veiculo()

    def test_status_atrasado_por_km(self):
        plano = PlanoManutencao.objects.create(
            veiculo=self.veiculo, descricao='Óleo',
            intervalo_km=10000, km_referencia=70000)
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
        self.veiculo = self.cria_veiculo()

    def test_novo_abastecimento(self):
        r = self.client.post(reverse('novo_abastecimento', args=[self.veiculo.id]), {
            'data': '2024-01-01', 'quilometragem': 1000, 'litros': '30.000',
            'valor_total': '180.00', 'tipo_combustivel': 'gasolina', 'posto': 'Shell'})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(Abastecimento.objects.count(), 1)

    def test_plano_exige_algum_intervalo(self):
        r = self.client.post(reverse('novo_plano_manutencao', args=[self.veiculo.id]),
                             {'descricao': 'Sem intervalo'})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(PlanoManutencao.objects.count(), 0)

    def test_detalhes_renderiza_com_dominio(self):
        Abastecimento.objects.create(
            veiculo=self.veiculo, quilometragem=1000, litros=30,
            valor_total=180, data='2024-01-01')
        r = self.client.get(reverse('detalhes_veiculo', args=[self.veiculo.id]))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Consumo médio')


class CombustivelFonteUnicaTests(LogadoMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.veiculo = self.cria_veiculo()

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
        Custo.objects.create(veiculo=v, tipo='outro', descricao='x',
                             valor=1200, data=date.today().replace(day=10))
        info = v.custo_vs_meta()
        self.assertEqual(info['pct'], 120)
        self.assertEqual(info['cor'], 'red')
        self.assertEqual(info['pct_barra'], 100)

    def test_sem_meta_retorna_none(self):
        self.assertIsNone(cria_veiculo().custo_vs_meta())


class DashboardTests(LogadoMixin, TestCase):
    def test_dashboard_renderiza(self):
        self.cria_veiculo()
        r = self.client.get(reverse('dashboard'))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Painel de Gestão')

    def test_dashboard_tem_projecao(self):
        r = self.client.get(reverse('dashboard'))
        self.assertIn('projecao_fechamento', r.context)
        self.assertContains(r, 'Projeção de fechamento')

    def test_relatorios_renderiza(self):
        self.assertEqual(self.client.get(reverse('relatorios')).status_code, 200)

    def test_exportar_csv(self):
        veiculo = self.cria_veiculo()
        Custo.objects.create(veiculo=veiculo, tipo='manutencao',
                             descricao='Revisao', valor=100, data='2024-01-01')
        r = self.client.get(reverse('exportar_custos'), {'formato': 'csv'})
        self.assertEqual(r.status_code, 200)
        self.assertIn('text/csv', r['Content-Type'])
        self.assertIn('Revisao', r.content.decode('utf-8'))

    def test_exportar_xlsx(self):
        veiculo = self.cria_veiculo()
        Custo.objects.create(veiculo=veiculo, tipo='manutencao',
                             descricao='Revisao', valor=100, data='2024-01-01')
        r = self.client.get(reverse('exportar_custos'), {'formato': 'xlsx'})
        self.assertEqual(r.status_code, 200)
        self.assertIn('spreadsheetml', r['Content-Type'])


class GruposTests(TestCase):
    def test_criar_grupos(self):
        from django.contrib.auth.models import Group
        from django.core.management import call_command

        call_command('criar_grupos')
        nomes = set(Group.objects.values_list('name', flat=True))
        self.assertEqual(nomes, {'Administrador', 'Gestor', 'Operador', 'Consulta'})
        consulta = Group.objects.get(name='Consulta')
        for perm in consulta.permissions.all():
            self.assertTrue(perm.codename.startswith('view_'))


class AuditoriaTests(TestCase):
    def test_alteracao_gera_log(self):
        from auditlog.models import LogEntry
        veiculo = cria_veiculo()
        self.assertTrue(LogEntry.objects.get_for_object(veiculo).exists())


class CriarAdminTests(TestCase):
    def test_cria_e_e_idempotente(self):
        import os
        from django.contrib.auth import get_user_model
        from django.core.management import call_command

        User_ = get_user_model()
        env = {
            'DJANGO_SUPERUSER_USERNAME': 'admin',
            'DJANGO_SUPERUSER_PASSWORD': 'senhaForte123',
            'DJANGO_SUPERUSER_EMAIL': 'admin@exemplo.com',
        }
        antigo = {k: os.environ.get(k) for k in env}
        os.environ.update(env)
        try:
            call_command('criar_admin')
            u = User_.objects.get(username='admin')
            self.assertTrue(u.is_superuser)
            self.assertTrue(hasattr(u, 'perfil'))  # org/perfil garantidos
            call_command('criar_admin')
            self.assertEqual(User_.objects.filter(username='admin').count(), 1)
        finally:
            for k, v in antigo.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v

    def test_sem_variaveis_nao_cria(self):
        from django.contrib.auth import get_user_model
        from django.core.management import call_command
        call_command('criar_admin')
        self.assertEqual(get_user_model().objects.filter(is_superuser=True).count(), 0)
