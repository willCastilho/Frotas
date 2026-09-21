"""Carga de massa sintetica de manutencao para o Gestao de Frotas.

Le um JSON (arquivo local ou URL) com veiculos e o historico deles e grava no
padrao dos modelos do app `carro`: a manutencao vira Custo(tipo='manutencao'),
as leituras de odometro viram RegistroQuilometragem (fonte de km_atual() e
custo_por_km()), os abastecimentos viram Abastecimento + o Custo espelho de
combustivel, os planos preventivos viram PlanoManutencao, e os motoristas e o
historico de vinculos viram Motorista e AtribuicaoVeiculo.

Pensado para rodar tambem em producao:

- Todo o conteudo fica isolado em uma organizacao propria, entao a frota real
  de outra organizacao nao e tocada.
- Se a organizacao de destino ja tiver veiculos fora do arquivo, o comando
  aborta e so prossegue com --confirmar.
- --criar-gestor cria o login que enxerga essa organizacao.
- --remover desfaz a carga (apaga os veiculos e os motoristas do arquivo na
  organizacao; os vinculos saem em cascata).
- Os filhos entram por bulk_create e por isso nao geram entrada no auditlog,
  que depende do sinal post_save. E o desejado para massa de demonstracao.
- O Abastecimento.save() cria o Custo de combustivel espelhado; como o
  bulk_create nao chama save(), o comando cria o par Custo+Abastecimento ja
  vinculado, com o mesmo texto de descricao, sem contagem dupla.

Exemplos:

    python manage.py popular_frota --dry-run
    python manage.py popular_frota --organizacao-nome "SMS - Demonstracao" \\
        --criar-gestor demo.frotas
    python manage.py popular_frota --url https://exemplo/frota_manutencoes.json \\
        --organizacao 3 --limpar
    python manage.py popular_frota --organizacao-nome "SMS - Demonstracao" --remover
    python manage.py popular_frota --organizacao-nome "SMS - Demonstracao" \\
        --limpar --sem-atribuicoes
"""

import json
import urllib.request
from datetime import datetime, time
from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from django.utils.crypto import get_random_string

from contas.models import Organizacao, PerfilUsuario

from carro.models import (
    Abastecimento,
    AtribuicaoVeiculo,
    Custo,
    Motorista,
    PlanoManutencao,
    RegistroQuilometragem,
    Veiculo,
)

CAMPOS_VEICULO = (
    'marca', 'modelo', 'ano', 'cor', 'placa', 'renavam', 'chassi',
    'combustivel', 'data_compra', 'valor_aquisicao', 'status',
    'meta_custo_mensal', 'observacoes',
)

CAMPOS_MOTORISTA = (
    'nome', 'cpf', 'cnh', 'cnh_categoria', 'cnh_validade', 'telefone',
    'email', 'status', 'observacoes',
)


class Command(BaseCommand):
    help = ('Popula veiculos, custos de manutencao, leituras de km e planos '
            'preventivos a partir de um JSON (arquivo ou URL). Idempotente: '
            'veiculo cuja placa ja existe na organizacao e pulado; use '
            '--limpar para recarregar ou --remover para desfazer.')

    def add_arguments(self, parser):
        parser.add_argument(
            '--arquivo', default='dados/frota_demo.json',
            help='Caminho do JSON (padrao: dados/frota_demo.json).')
        parser.add_argument(
            '--url', default=None,
            help='Baixa o JSON desta URL em vez de ler do disco.')
        parser.add_argument(
            '--organizacao', type=int, default=None,
            help='ID da organizacao de destino.')
        parser.add_argument(
            '--organizacao-nome', default=None,
            help='Nome da organizacao de destino; criada se nao existir.')
        parser.add_argument(
            '--criar-gestor', default=None, metavar='USUARIO',
            help='Cria (ou reaproveita) um login de gestor nessa organizacao.')
        parser.add_argument(
            '--senha', default=None,
            help='Senha do gestor. Se omitida, uma senha aleatoria e exibida.')
        parser.add_argument(
            '--sem-abastecimentos', action='store_true',
            help='Carrega so manutencao, km e planos (ignora os abastecimentos).')
        parser.add_argument(
            '--sem-motoristas', action='store_true',
            help='Nao carrega motoristas nem vinculos.')
        parser.add_argument(
            '--sem-atribuicoes', action='store_true',
            help='Carrega os motoristas, mas nao os vinculos com veiculos.')
        parser.add_argument(
            '--limpar', action='store_true',
            help='Apaga os veiculos dessas placas na organizacao antes de inserir.')
        parser.add_argument(
            '--remover', action='store_true',
            help='Apenas remove os veiculos do arquivo na organizacao e sai.')
        parser.add_argument(
            '--confirmar', action='store_true',
            help='Autoriza gravar em organizacao que ja tem veiculos proprios.')
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Executa tudo e faz rollback no final.')

    def handle(self, *args, **options):
        dados = self._carregar(options)
        organizacao = self._resolver_organizacao(options, dados)
        self.stdout.write(f'Organizacao: {organizacao} (id={organizacao.pk})')

        placas = [v['placa'].upper().strip()
                  for v in dados['veiculos'] if v.get('placa')]
        cpfs = [m['cpf'] for m in dados.get('motoristas', []) if m.get('cpf')]

        if options['remover']:
            return self._remover(organizacao, placas, cpfs, options['dry_run'])

        self._checar_frota_existente(organizacao, placas, options['confirmar'])

        total = {'veiculos': 0, 'custos': 0, 'km': 0, 'planos': 0, 'abast': 0,
                 'motoristas': 0, 'vinculos': 0}
        veiculos_criados = {}
        soma = Decimal('0.00')

        try:
            with transaction.atomic():
                if options['limpar']:
                    apagados, _ = Veiculo.objects.filter(
                        organizacao=organizacao, placa__in=placas).delete()
                    apagados_m, _ = Motorista.objects.filter(
                        organizacao=organizacao, cpf__in=cpfs).delete()
                    self.stdout.write(
                        f'Removidos {apagados + apagados_m} registros de '
                        f'veiculos e motoristas do arquivo.')

                for item in dados['veiculos']:
                    resultado = self._criar_veiculo(
                        organizacao, item, options['limpar'],
                        options['sem_abastecimentos'])
                    if resultado is None:
                        continue
                    veiculo, contagem, valor = resultado
                    veiculos_criados[veiculo.placa] = veiculo
                    total['veiculos'] += 1
                    for chave in ('custos', 'km', 'planos', 'abast'):
                        total[chave] += contagem[chave]
                    soma += valor
                    self.stdout.write(
                        f'  {veiculo.placa} {veiculo.marca} {veiculo.modelo} '
                        f"({veiculo.ano}) -> {contagem['custos']} custos, "
                        f"{contagem['abast']} abastecimentos, {contagem['km']} "
                        f"leituras, {contagem['planos']} planos")

                if not options['sem_motoristas'] and dados.get('motoristas'):
                    motoristas = self._criar_motoristas(
                        organizacao, dados['motoristas'])
                    total['motoristas'] = len(motoristas)
                    if not options['sem_atribuicoes']:
                        total['vinculos'] = self._criar_atribuicoes(
                            dados.get('atribuicoes', []),
                            veiculos_criados, motoristas)
                    self.stdout.write(
                        f"  Motoristas: {total['motoristas']} | "
                        f"vinculos: {total['vinculos']}")

                if options['criar_gestor']:
                    self._criar_gestor(
                        organizacao, options['criar_gestor'], options['senha'])

                if options['dry_run']:
                    raise _Rollback()
        except _Rollback:
            self.stdout.write(self.style.WARNING('DRY-RUN: nada foi gravado.'))
        else:
            self.stdout.write(self.style.SUCCESS('Carga concluida.'))

        self.stdout.write(
            f"Veiculos: {total['veiculos']} | custos: {total['custos']} "
            f"(inclui {total['abast']} de combustivel) | leituras de km: "
            f"{total['km']} | planos: {total['planos']} | "
            f"motoristas: {total['motoristas']} | vinculos: {total['vinculos']} | "
            f'total lancado: R$ {soma:,.2f}')

    # ------------------------------------------------------------------ dados

    def _carregar(self, options):
        if options['url']:
            self.stdout.write(f"Baixando {options['url']} ...")
            try:
                with urllib.request.urlopen(options['url'], timeout=60) as resp:
                    dados = json.loads(resp.read().decode('utf-8'))
            except Exception as exc:
                raise CommandError(f'Falha ao baixar o JSON: {exc}')
        else:
            caminho = Path(options['arquivo'])
            if not caminho.exists():
                raise CommandError(
                    f'Arquivo nao encontrado: {caminho}. Informe --arquivo ou --url.')
            with caminho.open(encoding='utf-8') as fh:
                dados = json.load(fh)

        if not isinstance(dados.get('veiculos'), list) or not dados['veiculos']:
            raise CommandError('JSON invalido: esperada a lista "veiculos".')
        return dados

    def _resolver_organizacao(self, options, dados):
        if options['organizacao']:
            try:
                return Organizacao.objects.get(pk=options['organizacao'])
            except Organizacao.DoesNotExist:
                raise CommandError(
                    f"Organizacao id={options['organizacao']} nao existe.")

        nome = options['organizacao_nome']
        if nome:
            org, criada = Organizacao.objects.get_or_create(nome=nome)
            if criada:
                self.stdout.write(self.style.SUCCESS(f'Organizacao "{nome}" criada.'))
            return org

        existentes = list(Organizacao.objects.all()[:10])
        if len(existentes) == 1:
            return existentes[0]
        if not existentes:
            nome = dados.get('organizacao_sugerida', 'Organizacao de testes')
            org = Organizacao.objects.create(nome=nome)
            self.stdout.write(self.style.SUCCESS(f'Organizacao "{nome}" criada.'))
            return org

        opcoes = ', '.join(f'{o.pk}={o.nome}' for o in existentes)
        raise CommandError(
            'Ha mais de uma organizacao; informe --organizacao <id> ou '
            f'--organizacao-nome. Opcoes: {opcoes}')

    def _checar_frota_existente(self, organizacao, placas, confirmar):
        """Evita despejar massa sintetica em cima de uma frota real."""
        proprios = (Veiculo.objects
                    .filter(organizacao=organizacao)
                    .exclude(placa__in=placas)
                    .count())
        if proprios and not confirmar:
            raise CommandError(
                f'A organizacao "{organizacao}" ja tem {proprios} veiculo(s) que '
                'nao estao no arquivo. Use uma organizacao separada '
                '(--organizacao-nome "SMS - Demonstracao") ou repita com '
                '--confirmar para gravar mesmo assim.')

    # ------------------------------------------------------------------ carga

    def _criar_veiculo(self, organizacao, item, limpar, sem_abastecimentos=False):
        placa = (item.get('placa') or '').upper().strip()
        if placa and Veiculo.objects.filter(
                organizacao=organizacao, placa=placa).exists():
            if not limpar:
                self.stdout.write(self.style.WARNING(
                    f'  {placa} ja existe na organizacao - pulado '
                    f'(use --limpar para recarregar).'))
                return None

        campos = {c: item[c] for c in CAMPOS_VEICULO if c in item}
        veiculo = Veiculo.objects.create(organizacao=organizacao, **campos)

        custos = [
            Custo(
                veiculo=veiculo,
                tipo=c.get('tipo', 'manutencao'),
                descricao=c['descricao'],
                valor=Decimal(str(c['valor'])),
                data=c['data'],
                quilometragem=c.get('quilometragem'),
                fornecedor=c.get('fornecedor', ''),
                forma_pagamento=c.get('forma_pagamento', ''),
            )
            for c in item.get('custos', [])
        ]
        Custo.objects.bulk_create(custos, batch_size=500)

        leituras = [
            RegistroQuilometragem(
                veiculo=veiculo,
                data=r['data'],
                quilometragem=r['quilometragem'],
                origem=r.get('origem', ''),
                observacao=r.get('observacao', ''),
            )
            for r in item.get('registros_km', [])
        ]
        RegistroQuilometragem.objects.bulk_create(leituras, batch_size=500)

        planos = [
            PlanoManutencao(
                veiculo=veiculo,
                descricao=p['descricao'],
                intervalo_km=p.get('intervalo_km'),
                intervalo_dias=p.get('intervalo_dias'),
                km_referencia=p.get('km_referencia'),
                data_referencia=p.get('data_referencia'),
            )
            for p in item.get('planos_manutencao', [])
        ]
        PlanoManutencao.objects.bulk_create(planos, batch_size=500)

        n_abast = 0
        if not sem_abastecimentos and item.get('abastecimentos'):
            n_abast, valor_combustivel = self._criar_abastecimentos(
                veiculo, item['abastecimentos'])
        else:
            valor_combustivel = Decimal('0.00')

        valor = sum((c.valor for c in custos), Decimal('0.00')) + valor_combustivel
        contagem = {'custos': len(custos) + n_abast, 'km': len(leituras),
                    'planos': len(planos), 'abast': n_abast}
        return veiculo, contagem, valor

    def _criar_abastecimentos(self, veiculo, registros):
        """Cria o par Custo(combustivel) + Abastecimento ja vinculado.

        Reproduz o que Abastecimento.save() faria, inclusive o texto da
        descricao, porque o bulk_create nao dispara o save().
        """
        custos = []
        for a in registros:
            litros = Decimal(str(a['litros']))
            posto = a.get('posto', '')
            custos.append(Custo(
                veiculo=veiculo,
                tipo='combustivel',
                valor=Decimal(str(a['valor_total'])),
                data=a['data'],
                quilometragem=a['quilometragem'],
                fornecedor=posto,
                descricao=(f'Abastecimento de {litros} L'
                           + (f' em {posto}' if posto else '')),
            ))
        custos = Custo.objects.bulk_create(custos, batch_size=500)

        abastecimentos = [
            Abastecimento(
                veiculo=veiculo,
                data=a['data'],
                quilometragem=a['quilometragem'],
                litros=Decimal(str(a['litros'])),
                valor_total=Decimal(str(a['valor_total'])),
                tipo_combustivel=a.get('tipo_combustivel', 'gasolina'),
                posto=a.get('posto', ''),
                custo=custo,
            )
            for a, custo in zip(registros, custos)
        ]
        Abastecimento.objects.bulk_create(abastecimentos, batch_size=500)

        total = sum((c.valor for c in custos), Decimal('0.00'))
        return len(abastecimentos), total

    def _criar_motoristas(self, organizacao, registros):
        """Cria os motoristas do arquivo. CPF ja cadastrado na organizacao e
        pulado (use --limpar para recarregar)."""
        existentes = set(Motorista.objects.filter(
            organizacao=organizacao,
            cpf__in=[m['cpf'] for m in registros],
        ).values_list('cpf', flat=True))

        novos = []
        for m in registros:
            if m['cpf'] in existentes:
                self.stdout.write(self.style.WARNING(
                    f"  Motorista {m['nome']} ({m['cpf']}) ja existe - pulado."))
                continue
            campos = {c: m[c] for c in CAMPOS_MOTORISTA if c in m}
            if m.get('data_cadastro'):
                dia = datetime.fromisoformat(m['data_cadastro']).date()
                campos['data_cadastro'] = timezone.make_aware(
                    datetime.combine(dia, time(8, 0)))
            novos.append(Motorista(organizacao=organizacao, **campos))

        novos = Motorista.objects.bulk_create(novos, batch_size=500)
        return {m.cpf: m for m in novos}

    def _criar_atribuicoes(self, registros, veiculos, motoristas):
        """Cria os vinculos cujo veiculo e motorista foram criados nesta carga.
        O arquivo ja vem sem sobreposicao por veiculo e por motorista, que e a
        regra aplicada pela tela de vinculo."""
        objetos = []
        for a in registros:
            veiculo = veiculos.get(a['placa'].upper().strip())
            motorista = motoristas.get(a['cpf'])
            if veiculo is None or motorista is None:
                continue
            objetos.append(AtribuicaoVeiculo(
                veiculo=veiculo,
                motorista=motorista,
                data_inicio=a['data_inicio'],
                data_fim=a.get('data_fim'),
                observacao=a.get('observacao', ''),
            ))
        AtribuicaoVeiculo.objects.bulk_create(objetos, batch_size=500)
        return len(objetos)

    def _criar_gestor(self, organizacao, username, senha):
        User = get_user_model()
        user = User.objects.filter(username=username).first()
        senha_exibir = senha or get_random_string(12)

        if user is None:
            user = User.objects.create_user(username=username, password=senha_exibir)
            criado = True
        else:
            criado = False
            if senha:
                user.set_password(senha)
                user.save(update_fields=['password'])

        perfil, _ = PerfilUsuario.objects.get_or_create(
            user=user,
            defaults={'papel': PerfilUsuario.PAPEL_GESTOR, 'organizacao': organizacao})
        if perfil.organizacao_id != organizacao.pk or not perfil.eh_gestor:
            perfil.organizacao = organizacao
            perfil.papel = PerfilUsuario.PAPEL_GESTOR
            perfil.save(update_fields=['organizacao', 'papel'])

        if criado or senha:
            self.stdout.write(self.style.SUCCESS(
                f'Gestor "{username}" pronto - senha: {senha_exibir}'))
        else:
            self.stdout.write(self.style.SUCCESS(
                f'Gestor "{username}" ja existia; senha mantida e perfil '
                f'apontado para "{organizacao}".'))

    # --------------------------------------------------------------- remocao

    def _remover(self, organizacao, placas, cpfs, dry_run):
        try:
            with transaction.atomic():
                apagados, detalhe = Veiculo.objects.filter(
                    organizacao=organizacao, placa__in=placas).delete()
                apagados_m, detalhe_m = Motorista.objects.filter(
                    organizacao=organizacao, cpf__in=cpfs).delete()
                apagados += apagados_m
                for modelo, qtd in detalhe_m.items():
                    detalhe[modelo] = detalhe.get(modelo, 0) + qtd
                if dry_run:
                    raise _Rollback()
        except _Rollback:
            self.stdout.write(self.style.WARNING(
                f'DRY-RUN: seriam removidos {apagados} registros.'))
            return

        self.stdout.write(self.style.SUCCESS(
            f'Removidos {apagados} registros da organizacao "{organizacao}".'))
        for modelo, quantidade in sorted(detalhe.items()):
            self.stdout.write(f'  {modelo}: {quantidade}')


class _Rollback(Exception):
    """Sinaliza o rollback do --dry-run."""
