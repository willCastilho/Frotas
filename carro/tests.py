from datetime import date, timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from carro.forms import CustoForm, VeiculoForm
from carro.models import (
    Abastecimento,
    Custo,
    Documento,
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
    # Gestor = administrador da organizacao (perfil padrao dos testes).
    papel = PerfilUsuario.PAPEL_GESTOR

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
            user=self.user_b, organizacao=self.org_b, papel='gestor')
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
        self.assertEqual(user.perfil.papel, 'gestor')

    def test_usuario_sem_org_vai_para_onboarding(self):
        User.objects.create_user('semorg', password='senha12345')
        self.client.login(username='semorg', password='senha12345')
        r = self.client.get(reverse('home'))
        self.assertEqual(r.status_code, 302)
        self.assertIn(reverse('criar_organizacao'), r.url)


class RBACTests(LogadoMixin, TestCase):
    papel = PerfilUsuario.PAPEL_OPERADOR

    def test_operador_nao_cria_veiculo(self):
        r = self.client.post(reverse('novo_veiculo'), {
            'marca': 'Fiat', 'modelo': 'Uno', 'ano': 2015, 'cor': 'Branco',
            'data_compra': '2020-01-01', 'status': 'ativo',
        })
        self.assertEqual(r.status_code, 302)
        self.assertEqual(Veiculo.objects.count(), 0)

    def test_operador_sem_veiculo_ve_aviso(self):
        r = self.client.get(reverse('home'))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Nenhum veículo vinculado')

    def test_operador_nao_acessa_dashboard(self):
        r = self.client.get(reverse('dashboard'))
        self.assertEqual(r.status_code, 302)


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


class CadastroCompletoTests(LogadoMixin, TestCase):
    def _dados(self, **extra):
        base = {
            'marca': 'Fiat', 'modelo': 'Toro', 'ano': 2021, 'cor': 'Vermelho',
            'data_compra': '2021-01-01', 'status': 'ativo',
        }
        base.update(extra)
        return base

    def test_cadastra_com_placa_e_documentos(self):
        r = self.client.post(reverse('novo_veiculo'), self._dados(
            placa='abc1d23', renavam='123456789', chassi='9BWHE21JX24060831',
            combustivel='flex', valor_aquisicao='95000.00',
            observacoes='Único dono'))
        self.assertEqual(r.status_code, 302)
        v = Veiculo.objects.get(modelo='Toro')
        self.assertEqual(v.placa, 'ABC1D23')  # normalizada em maiuscula
        self.assertEqual(v.combustivel, 'flex')
        self.assertEqual(float(v.valor_aquisicao), 95000.0)

    def test_placa_unica_por_org(self):
        self.cria_veiculo(placa='XYZ1A11')
        r = self.client.post(reverse('novo_veiculo'), self._dados(placa='xyz1a11'))
        self.assertEqual(r.status_code, 200)  # form invalido, re-render
        self.assertContains(r, 'Já existe um veículo com esta placa')

    def test_placa_pode_repetir_entre_orgs(self):
        outra = cria_org('Outra')
        cria_veiculo(org=outra, placa='SAME123')
        r = self.client.post(reverse('novo_veiculo'), self._dados(placa='same123'))
        self.assertEqual(r.status_code, 302)  # permitido: outra organizacao

    def test_busca_por_placa(self):
        self.cria_veiculo(modelo='Palio', placa='BRA2E19')
        r = self.client.get(reverse('home'), {'search': 'BRA2E19'})
        self.assertContains(r, 'Palio')


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


class DocumentoTests(LogadoMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.veiculo = self.cria_veiculo()

    def test_status_vencido(self):
        d = Documento.objects.create(
            veiculo=self.veiculo, tipo='ipva',
            vencimento=date.today() - timedelta(days=5))
        self.assertEqual(d.status()['cor'], 'red')

    def test_status_vence_em_breve(self):
        d = Documento.objects.create(
            veiculo=self.veiculo, tipo='seguro',
            vencimento=date.today() + timedelta(days=20))
        self.assertEqual(d.status()['cor'], 'yellow')

    def test_status_em_dia(self):
        d = Documento.objects.create(
            veiculo=self.veiculo, tipo='licenciamento',
            vencimento=date.today() + timedelta(days=200))
        self.assertEqual(d.status()['cor'], 'green')

    def test_criar_documento_pela_view(self):
        r = self.client.post(reverse('novo_documento', args=[self.veiculo.id]), {
            'tipo': 'licenciamento',
            'vencimento': (date.today() + timedelta(days=40)).isoformat(),
            'observacao': 'Anual'})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(Documento.objects.count(), 1)


class Agenda90Tests(LogadoMixin, TestCase):
    def test_agenda_lista_doc_e_manutencao(self):
        v = self.cria_veiculo()
        Documento.objects.create(veiculo=v, tipo='ipva',
                                 vencimento=date.today() + timedelta(days=30))
        # Manutencao por data vencendo em ~10 dias
        PlanoManutencao.objects.create(
            veiculo=v, descricao='Licenciamento', intervalo_dias=30,
            data_referencia=date.today() - timedelta(days=20))
        # Documento fora da janela (nao deve aparecer)
        Documento.objects.create(veiculo=v, tipo='seguro',
                                 vencimento=date.today() + timedelta(days=200))
        r = self.client.get(reverse('dashboard'))
        agenda = r.context['agenda_90']
        categorias = {i['categoria'] for i in agenda}
        self.assertEqual(categorias, {'Documento', 'Manutenção'})
        self.assertEqual(len(agenda), 2)  # o seguro de 200 dias fica de fora
        self.assertContains(r, 'Próximos 90 dias')
        # O painel separado de alertas de manutencao foi consolidado na agenda.
        self.assertNotContains(r, 'Alertas de manutenção')

    def test_manutencao_por_km_atrasada_entra_na_agenda(self):
        v = self.cria_veiculo()
        # Manutencao so por km, atrasada (referencia + intervalo < km atual).
        PlanoManutencao.objects.create(
            veiculo=v, descricao='Troca de óleo', intervalo_km=10000,
            km_referencia=0)
        RegistroQuilometragem.objects.create(
            veiculo=v, data=date.today(), quilometragem=15000)
        agenda = self.client.get(reverse('dashboard')).context['agenda_90']
        itens = [i for i in agenda if i['titulo'] == 'Troca de óleo']
        self.assertEqual(len(itens), 1)
        self.assertIsNone(itens[0]['data'])   # sem data: alerta por km
        self.assertEqual(itens[0]['cor'], 'red')


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


class CustoRecorrenteTests(LogadoMixin, TestCase):
    def test_parcelado_divide_valor(self):
        veiculo = self.cria_veiculo()
        r = self.client.post(reverse('novo_custo', args=[veiculo.id]), {
            'tipo': 'ipva', 'descricao': 'IPVA 2026', 'valor': '1000.00',
            'data': '2026-01-10', 'recorrencia': 'parcelado', 'ocorrencias': '4',
        })
        self.assertEqual(r.status_code, 302)
        custos = Custo.objects.filter(veiculo=veiculo).order_by('data')
        self.assertEqual(custos.count(), 4)
        # A soma das parcelas bate exatamente com o total.
        self.assertEqual(sum(float(c.valor) for c in custos), 1000.0)
        # Parcelas em meses consecutivos.
        self.assertEqual([c.data.month for c in custos], [1, 2, 3, 4])
        self.assertEqual(custos.first().parcela_total, 4)

    def test_recorrencia_mensal_repete_valor(self):
        veiculo = self.cria_veiculo()
        self.client.post(reverse('novo_custo', args=[veiculo.id]), {
            'tipo': 'seguro', 'descricao': 'Seguro', 'valor': '300.00',
            'data': '2026-01-15', 'recorrencia': 'mensal', 'ocorrencias': '3',
        })
        custos = Custo.objects.filter(veiculo=veiculo)
        self.assertEqual(custos.count(), 3)
        self.assertTrue(all(float(c.valor) == 300.0 for c in custos))

    def test_unico_nao_gera_serie(self):
        veiculo = self.cria_veiculo()
        self.client.post(reverse('novo_custo', args=[veiculo.id]), {
            'tipo': 'manutencao', 'descricao': 'Revisao', 'valor': '250.00',
            'data': '2026-01-15', 'recorrencia': 'nenhuma', 'ocorrencias': '1',
        })
        self.assertEqual(Custo.objects.filter(veiculo=veiculo).count(), 1)


class DepreciacaoTests(TestCase):
    def test_valor_estimado_menor_que_aquisicao(self):
        veiculo = cria_veiculo(
            data_compra=date.today() - timedelta(days=730),
            valor_aquisicao='100000.00')
        info = veiculo.valor_estimado_atual()
        self.assertIsNotNone(info)
        self.assertLess(info['atual'], 100000.0)
        self.assertGreater(info['atual'], 0)
        self.assertGreater(info['pct'], 0)

    def test_sem_valor_aquisicao_retorna_none(self):
        veiculo = cria_veiculo()
        self.assertIsNone(veiculo.valor_estimado_atual())


class RelatorioPDFTests(LogadoMixin, TestCase):
    def test_exportar_pdf(self):
        veiculo = self.cria_veiculo()
        Custo.objects.create(veiculo=veiculo, tipo='manutencao',
                             descricao='Revisao', valor=100, data='2024-01-01')
        r = self.client.get(reverse('exportar_custos'), {'formato': 'pdf'})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r['Content-Type'], 'application/pdf')
        self.assertTrue(r.content.startswith(b'%PDF'))


class DashboardPeriodoTests(LogadoMixin, TestCase):
    def test_periodo_mes_anterior_sem_projecao(self):
        r = self.client.get(reverse('dashboard'), {'periodo': 'mes_anterior'})
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.context['mostrar_projecao'])
        self.assertNotContains(r, 'Projeção de fechamento')

    def test_periodo_filtra_custos(self):
        veiculo = self.cria_veiculo()
        Custo.objects.create(veiculo=veiculo, tipo='manutencao',
                             descricao='Antigo', valor=500, data='2020-01-01')
        r = self.client.get(reverse('dashboard'),
                            {'periodo': 'custom', 'inicio': '2026-01-01'})
        # Custo de 2020 fica fora do periodo escolhido.
        self.assertEqual(float(r.context['custo_mes_total']), 0.0)


class MotoristaTests(LogadoMixin, TestCase):
    def _cria_motorista(self, nome='João Motorista'):
        from carro.models import Motorista
        return Motorista.objects.create(organizacao=self.org, nome=nome)

    def test_cadastro_pela_view(self):
        r = self.client.post(reverse('novo_motorista'), {
            'nome': 'Maria Silva', 'cnh': '12345678900',
            'cnh_categoria': 'B', 'status': 'ativo',
        })
        self.assertEqual(r.status_code, 302)
        from carro.models import Motorista
        m = Motorista.objects.get(nome='Maria Silva')
        self.assertEqual(m.organizacao, self.org)

    def test_isolamento_por_organizacao(self):
        from carro.models import Motorista
        outra = cria_org('Outra')
        Motorista.objects.create(organizacao=outra, nome='De Fora')
        self._cria_motorista('Meu Motorista')
        r = self.client.get(reverse('motoristas'))
        self.assertContains(r, 'Meu Motorista')
        self.assertNotContains(r, 'De Fora')

    def test_vinculo_define_motorista_atual(self):
        veiculo = self.cria_veiculo()
        m = self._cria_motorista()
        r = self.client.post(reverse('nova_atribuicao'), {
            'motorista': m.id, 'veiculo': veiculo.id,
            'data_inicio': date.today().isoformat(),
        })
        self.assertEqual(r.status_code, 302)
        self.assertEqual(veiculo.motorista_atual(), m)

    def test_troca_encerra_vinculo_anterior(self):
        from carro.models import AtribuicaoVeiculo
        veiculo = self.cria_veiculo()
        m1 = self._cria_motorista('Primeiro')
        m2 = self._cria_motorista('Segundo')
        self.client.post(reverse('nova_atribuicao'), {
            'motorista': m1.id, 'veiculo': veiculo.id,
            'data_inicio': (date.today() - timedelta(days=10)).isoformat(),
        })
        self.client.post(reverse('nova_atribuicao'), {
            'motorista': m2.id, 'veiculo': veiculo.id,
            'data_inicio': date.today().isoformat(),
        })
        # So o segundo fica em aberto; o primeiro foi encerrado automaticamente.
        abertos = AtribuicaoVeiculo.objects.filter(veiculo=veiculo, data_fim__isnull=True)
        self.assertEqual(abertos.count(), 1)
        self.assertEqual(veiculo.motorista_atual(), m2)

    def test_relatorio_motorista_por_data(self):
        from carro.models import AtribuicaoVeiculo
        veiculo = self.cria_veiculo()
        m = self._cria_motorista('Condutor X')
        # Vinculo de 01/03 a 31/03.
        AtribuicaoVeiculo.objects.create(
            veiculo=veiculo, motorista=m,
            data_inicio=date(2026, 3, 1), data_fim=date(2026, 3, 31))
        # Dentro do periodo: aparece.
        r = self.client.get(reverse('relatorio_motoristas'), {'data': '2026-03-15'})
        self.assertContains(r, 'Condutor X')
        # Fora do periodo: nao aparece na lista de alocacoes.
        r2 = self.client.get(reverse('relatorio_motoristas'), {'data': '2026-05-01'})
        alocacoes = list(r2.context['alocacoes'])
        self.assertEqual(alocacoes, [])

    def test_relatorio_exporta_csv(self):
        from carro.models import AtribuicaoVeiculo
        veiculo = self.cria_veiculo()
        m = self._cria_motorista('Exportado')
        AtribuicaoVeiculo.objects.create(
            veiculo=veiculo, motorista=m, data_inicio=date(2026, 1, 1))
        r = self.client.get(reverse('relatorio_motoristas'),
                            {'data': '2026-06-01', 'formato': 'csv'})
        self.assertEqual(r.status_code, 200)
        self.assertIn('text/csv', r['Content-Type'])
        self.assertIn('Exportado', r.content.decode('utf-8'))


class BrevoBackendTests(TestCase):
    def test_envia_via_api_http(self):
        import json
        from unittest.mock import patch
        from django.core.mail import EmailMessage
        from contas.email_backends import BrevoAPIBackend

        backend = BrevoAPIBackend()
        backend.api_key = 'chave-teste'
        msg = EmailMessage('Assunto', 'Corpo', 'Frotas <no-reply@ex.com>',
                           ['destino@ex.com'])
        capturado = {}

        class FakeResp:
            def __enter__(self): return self
            def __exit__(self, *a): return False
            def read(self): return b'{"messageId":"1"}'

        def fake_urlopen(req, timeout=15):
            capturado['url'] = req.full_url
            capturado['api_key'] = req.get_header('Api-key')
            capturado['body'] = json.loads(req.data.decode('utf-8'))
            return FakeResp()

        with patch('contas.email_backends.urllib.request.urlopen',
                   side_effect=fake_urlopen):
            enviados = backend.send_messages([msg])

        self.assertEqual(enviados, 1)
        self.assertIn('api.brevo.com', capturado['url'])
        self.assertEqual(capturado['api_key'], 'chave-teste')
        self.assertEqual(capturado['body']['to'], [{'email': 'destino@ex.com'}])
        self.assertEqual(capturado['body']['sender']['email'], 'no-reply@ex.com')

    def test_sem_chave_falha(self):
        from django.core.mail import EmailMessage
        from contas.email_backends import BrevoAPIBackend
        backend = BrevoAPIBackend()
        backend.api_key = ''
        with self.assertRaises(ValueError):
            backend.send_messages([EmailMessage('a', 'b', 'x@ex.com', ['y@ex.com'])])


class ConviteUsuarioTests(LogadoMixin, TestCase):
    def _convidar(self, **over):
        dados = {'username': 'convidado', 'email': 'novo@ex.com',
                 'papel': PerfilUsuario.PAPEL_GESTOR}
        dados.update(over)
        return self.client.post(reverse('usuarios'), dados, follow=True)

    def test_convite_cria_usuario_e_perfil(self):
        r = self._convidar()
        self.assertEqual(r.status_code, 200)
        novo = User.objects.get(username='convidado')
        self.assertFalse(novo.has_usable_password())
        self.assertEqual(novo.perfil.organizacao, self.org)
        self.assertEqual(novo.perfil.papel, PerfilUsuario.PAPEL_GESTOR)

    def test_convite_operador_liga_motorista(self):
        from carro.models import Motorista
        m = Motorista.objects.create(organizacao=self.org, nome='Zé')
        r = self._convidar(username='ze', email='ze@ex.com',
                           papel=PerfilUsuario.PAPEL_OPERADOR, motorista=m.id)
        self.assertEqual(r.status_code, 200)
        novo = User.objects.get(username='ze')
        self.assertEqual(novo.perfil.papel, PerfilUsuario.PAPEL_OPERADOR)
        m.refresh_from_db()
        self.assertEqual(m.user_id, novo.id)

    def test_convite_operador_exige_motorista(self):
        r = self._convidar(username='semmoto', email='sm@ex.com',
                           papel=PerfilUsuario.PAPEL_OPERADOR)
        self.assertFalse(User.objects.filter(username='semmoto').exists())

    def test_convite_mostra_link_na_tela(self):
        r = self._convidar()
        # O link de definir senha aparece na tela (garantia sem SMTP).
        self.assertContains(r, 'Link de acesso')
        self.assertContains(r, '/reset/')

    def test_convite_envia_email(self):
        from django.core import mail
        self._convidar(email='alvo@ex.com')
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('alvo@ex.com', mail.outbox[0].to)
        self.assertIn('/reset/', mail.outbox[0].body)

    def test_link_permite_definir_senha(self):
        self._convidar(email='fulano@ex.com')
        novo = User.objects.get(username='convidado')
        from django.contrib.auth.tokens import default_token_generator
        from django.utils.encoding import force_bytes
        from django.utils.http import urlsafe_base64_encode
        uid = urlsafe_base64_encode(force_bytes(novo.pk))
        token = default_token_generator.make_token(novo)
        # Token valido mesmo com senha inutilizavel (o bug antigo).
        self.assertTrue(default_token_generator.check_token(novo, token))
        url = reverse('password_reset_confirm',
                      kwargs={'uidb64': uid, 'token': token})
        # A pagina de confirmacao redireciona para o formulario 'set-password'.
        r = self.client.get(url, follow=True)
        self.assertEqual(r.status_code, 200)


class AdminGlobalTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user('root', password='raiz12345')
        PerfilUsuario.objects.create(
            user=self.admin, organizacao=None, papel=PerfilUsuario.PAPEL_ADMIN)
        self.client.login(username='root', password='raiz12345')

    def test_painel_renderiza(self):
        r = self.client.get(reverse('painel_admin'))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Administrador do Sistema')

    def test_dashboard_redireciona_para_painel(self):
        r = self.client.get(reverse('dashboard'))
        self.assertRedirects(r, reverse('painel_admin'))

    def test_impersonar_e_sair(self):
        org = cria_org('OrgX')
        u = User.objects.create_user('gestor1', password='x')
        p = PerfilUsuario.objects.create(
            user=u, organizacao=org, papel=PerfilUsuario.PAPEL_GESTOR)
        self.client.post(reverse('impersonar', args=[p.id]))
        # Navegando como gestor: dashboard acessivel e org efetiva = OrgX.
        r = self.client.get(reverse('dashboard'))
        self.assertEqual(r.status_code, 200)
        self.client.post(reverse('sair_impersonacao'))
        r2 = self.client.get(reverse('dashboard'))
        self.assertRedirects(r2, reverse('painel_admin'))

    def test_nao_impersona_outro_admin(self):
        outro = User.objects.create_user('root2', password='x')
        p = PerfilUsuario.objects.create(
            user=outro, organizacao=None, papel=PerfilUsuario.PAPEL_ADMIN)
        r = self.client.post(reverse('impersonar', args=[p.id]))
        self.assertEqual(r.status_code, 404)


class OperadorVeiculoTests(TestCase):
    def setUp(self):
        from carro.models import AtribuicaoVeiculo, Motorista
        self.org = cria_org('OrgOp')
        self.veiculo = cria_veiculo(org=self.org, modelo='Meu')
        self.outro = cria_veiculo(org=self.org, modelo='Alheio')
        self.user = User.objects.create_user('op', password='operad12345')
        PerfilUsuario.objects.create(
            user=self.user, organizacao=self.org, papel=PerfilUsuario.PAPEL_OPERADOR)
        self.motorista = Motorista.objects.create(
            organizacao=self.org, nome='Op', user=self.user)
        AtribuicaoVeiculo.objects.create(
            veiculo=self.veiculo, motorista=self.motorista, data_inicio=date.today())
        self.client.login(username='op', password='operad12345')

    def test_home_vai_para_seu_veiculo(self):
        r = self.client.get(reverse('home'))
        self.assertRedirects(r, reverse('detalhes_veiculo', args=[self.veiculo.id]))

    def test_nao_acessa_outro_veiculo(self):
        r = self.client.get(reverse('detalhes_veiculo', args=[self.outro.id]))
        self.assertEqual(r.status_code, 302)

    def test_lanca_abastecimento_no_seu_veiculo(self):
        r = self.client.post(reverse('novo_abastecimento', args=[self.veiculo.id]), {
            'data': '2026-01-01', 'quilometragem': 1000, 'litros': 40,
            'valor_total': 200, 'tipo_combustivel': 'gasolina'})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(self.veiculo.abastecimentos.count(), 1)

    def test_nao_lanca_no_veiculo_alheio(self):
        self.client.post(reverse('novo_abastecimento', args=[self.outro.id]), {
            'data': '2026-01-01', 'quilometragem': 1000, 'litros': 40,
            'valor_total': 200, 'tipo_combustivel': 'gasolina'})
        self.assertEqual(self.outro.abastecimentos.count(), 0)


class UmVeiculoPorMotoristaTests(LogadoMixin, TestCase):
    def test_novo_vinculo_fecha_o_anterior_do_motorista(self):
        from carro.models import AtribuicaoVeiculo, Motorista
        v1 = self.cria_veiculo(modelo='V1')
        v2 = self.cria_veiculo(modelo='V2')
        m = Motorista.objects.create(organizacao=self.org, nome='M')
        self.client.post(reverse('nova_atribuicao'), {
            'motorista': m.id, 'veiculo': v1.id, 'data_inicio': date.today().isoformat()})
        self.client.post(reverse('nova_atribuicao'), {
            'motorista': m.id, 'veiculo': v2.id, 'data_inicio': date.today().isoformat()})
        abertos = AtribuicaoVeiculo.objects.filter(motorista=m, data_fim__isnull=True)
        self.assertEqual(abertos.count(), 1)
        self.assertEqual(m.veiculo_atual(), v2)


class LogsTests(LogadoMixin, TestCase):
    def test_log_registra_criacao_com_login(self):
        self.client.post(reverse('novo_veiculo'), {
            'marca': 'Fiat', 'modelo': 'Uno', 'ano': 2015, 'cor': 'Branco',
            'data_compra': '2020-01-01', 'status': 'ativo'})
        r = self.client.get(reverse('logs'))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'teste')      # login do autor
        self.assertContains(r, 'Criação')    # tipo da acao


class AdminCRUDTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user('root', password='raiz12345')
        PerfilUsuario.objects.create(
            user=self.admin, organizacao=None, papel=PerfilUsuario.PAPEL_ADMIN)
        self.client.login(username='root', password='raiz12345')

    def test_cria_organizacao(self):
        r = self.client.post(reverse('nova_organizacao_admin'), {
            'nome': 'Nova Empresa', 'assinatura_ativa': 'on'})
        self.assertEqual(r.status_code, 302)
        self.assertTrue(Organizacao.objects.filter(nome='Nova Empresa').exists())

    def test_edita_organizacao(self):
        org = cria_org('Antiga')
        r = self.client.post(reverse('editar_organizacao', args=[org.id]), {
            'nome': 'Renomeada', 'assinatura_ativa': 'on'})
        self.assertEqual(r.status_code, 302)
        org.refresh_from_db()
        self.assertEqual(org.nome, 'Renomeada')

    def test_exclui_organizacao(self):
        org = cria_org('ParaExcluir')
        r = self.client.post(reverse('excluir_organizacao', args=[org.id]))
        self.assertEqual(r.status_code, 302)
        self.assertFalse(Organizacao.objects.filter(id=org.id).exists())

    def test_cria_usuario_gestor(self):
        org = cria_org('OrgU')
        r = self.client.post(reverse('novo_usuario_admin', args=[org.id]), {
            'username': 'g2', 'email': 'g2@ex.com',
            'papel': PerfilUsuario.PAPEL_GESTOR})
        self.assertEqual(r.status_code, 302)
        u = User.objects.get(username='g2')
        self.assertEqual(u.perfil.papel, PerfilUsuario.PAPEL_GESTOR)
        self.assertEqual(u.perfil.organizacao, org)

    def test_cria_usuario_admin_sem_org(self):
        org = cria_org('OrgU2')
        r = self.client.post(reverse('novo_usuario_admin', args=[org.id]), {
            'username': 'root2', 'email': 'root2@ex.com',
            'papel': PerfilUsuario.PAPEL_ADMIN})
        self.assertEqual(r.status_code, 302)
        u = User.objects.get(username='root2')
        self.assertEqual(u.perfil.papel, PerfilUsuario.PAPEL_ADMIN)
        self.assertIsNone(u.perfil.organizacao)
        self.assertTrue(u.is_superuser)

    def test_exclui_usuario(self):
        org = cria_org('OrgU3')
        alvo = User.objects.create_user('vitima', password='x')
        p = PerfilUsuario.objects.create(
            user=alvo, organizacao=org, papel=PerfilUsuario.PAPEL_GESTOR)
        r = self.client.post(reverse('excluir_usuario_admin', args=[p.id]))
        self.assertEqual(r.status_code, 302)
        self.assertFalse(User.objects.filter(username='vitima').exists())

    def test_cria_edita_exclui_veiculo(self):
        org = cria_org('OrgV')
        r = self.client.post(reverse('novo_veiculo_admin', args=[org.id]), {
            'marca': 'Fiat', 'modelo': 'Mobi', 'ano': 2022, 'cor': 'Vermelho',
            'data_compra': '2022-01-01', 'status': 'ativo'})
        self.assertEqual(r.status_code, 302)
        v = Veiculo.objects.get(modelo='Mobi')
        self.assertEqual(v.organizacao, org)
        # editar
        self.client.post(reverse('editar_veiculo_admin', args=[v.id]), {
            'marca': 'Fiat', 'modelo': 'Mobi Way', 'ano': 2022, 'cor': 'Vermelho',
            'data_compra': '2022-01-01', 'status': 'ativo'})
        v.refresh_from_db()
        self.assertEqual(v.modelo, 'Mobi Way')
        # excluir
        self.client.post(reverse('excluir_veiculo_admin', args=[v.id]))
        self.assertFalse(Veiculo.objects.filter(id=v.id).exists())

    def test_admin_sobe_logo_da_org(self):
        import io
        from django.core.files.uploadedfile import SimpleUploadedFile
        try:
            from PIL import Image
        except ImportError:
            self.skipTest('Pillow ausente')
        org = cria_org('OrgLogo')
        buf = io.BytesIO()
        Image.new('RGB', (10, 10), 'blue').save(buf, format='PNG')
        logo = SimpleUploadedFile('logo.png', buf.getvalue(), content_type='image/png')
        r = self.client.post(reverse('editar_organizacao', args=[org.id]), {
            'nome': 'OrgLogo', 'assinatura_ativa': 'on', 'logo': logo})
        self.assertEqual(r.status_code, 302)
        org.refresh_from_db()
        self.assertTrue(org.logo)

    def test_gestor_nao_acessa_crud_admin(self):
        org = cria_org('OrgG')
        u = User.objects.create_user('gestorx', password='x12345678')
        PerfilUsuario.objects.create(
            user=u, organizacao=org, papel=PerfilUsuario.PAPEL_GESTOR)
        self.client.logout()
        self.client.login(username='gestorx', password='x12345678')
        r = self.client.post(reverse('nova_organizacao_admin'), {'nome': 'Hack'})
        self.assertEqual(r.status_code, 302)
        self.assertFalse(Organizacao.objects.filter(nome='Hack').exists())


class GestorIdentidadeTests(LogadoMixin, TestCase):
    def test_gestor_atualiza_nome_e_logo(self):
        import io
        from django.core.files.uploadedfile import SimpleUploadedFile
        try:
            from PIL import Image
        except ImportError:
            self.skipTest('Pillow ausente')
        buf = io.BytesIO()
        Image.new('RGB', (8, 8), 'green').save(buf, format='PNG')
        logo = SimpleUploadedFile('l.png', buf.getvalue(), content_type='image/png')
        r = self.client.post(reverse('conta'), {'nome': 'Nova Marca', 'logo': logo})
        self.assertEqual(r.status_code, 302)
        self.org.refresh_from_db()
        self.assertEqual(self.org.nome, 'Nova Marca')
        self.assertTrue(self.org.logo)
