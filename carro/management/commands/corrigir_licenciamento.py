"""Corrige lancamentos de licenciamento que ficaram como PlanoManutencao.

O licenciamento (e demais documentos com vencimento) deve viver na secao
Documentos do veiculo, nao em "Manutencao Preventiva". Este comando varre os
PlanoManutencao cuja descricao contem "licenc", cria o Documento equivalente
(tipo=licenciamento, com o mesmo vencimento que a tela ja mostrava em
"Proxima") e apaga o plano.

E idempotente: se o Documento equivalente ja existir (mesmo veiculo, tipo e
vencimento) ele nao e duplicado. Roda em toda a base ou pode ser restrito a
uma organizacao. Sempre confira antes com --dry-run.

Exemplos:

    python manage.py corrigir_licenciamento --dry-run
    python manage.py corrigir_licenciamento
    python manage.py corrigir_licenciamento \\
        --organizacao-nome "SMS Caçador - Demonstração"
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from contas.models import Organizacao

from carro.models import Documento, PlanoManutencao


class Command(BaseCommand):
    help = ('Move planos de manutencao de licenciamento para a secao '
            'Documentos do veiculo. Idempotente.')

    def add_arguments(self, parser):
        parser.add_argument(
            '--organizacao', type=int, default=None,
            help='Restringe a correcao aos veiculos desta organizacao (id).')
        parser.add_argument(
            '--organizacao-nome', default=None,
            help='Restringe a correcao aos veiculos desta organizacao (nome).')
        parser.add_argument(
            '--termo', default='licenc',
            help='Texto (case-insensitive) que identifica o plano de '
                 'licenciamento na descricao. Padrao: "licenc".')
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Mostra o que seria feito e faz rollback no final.')

    def handle(self, *args, **options):
        planos = PlanoManutencao.objects.filter(
            descricao__icontains=options['termo']
        ).select_related('veiculo', 'veiculo__organizacao')

        org = self._resolver_organizacao(options)
        if org is not None:
            planos = planos.filter(veiculo__organizacao=org)
            self.stdout.write(f'Restrito a organizacao: {org} (id={org.pk})')

        planos = list(planos)
        if not planos:
            self.stdout.write(self.style.WARNING(
                'Nenhum plano de licenciamento encontrado. Nada a fazer.'))
            return

        criados = duplicados = sem_data = removidos = 0

        try:
            with transaction.atomic():
                for plano in planos:
                    vencimento = plano.proxima_data or plano.data_referencia
                    if vencimento is None:
                        sem_data += 1
                        self.stdout.write(self.style.WARNING(
                            f'  {plano.veiculo} - "{plano.descricao}" sem data '
                            f'de referencia; plano mantido para revisao manual.'))
                        continue

                    ja_existe = Documento.objects.filter(
                        veiculo=plano.veiculo,
                        tipo='licenciamento',
                        vencimento=vencimento,
                    ).exists()

                    if ja_existe:
                        duplicados += 1
                    else:
                        Documento.objects.create(
                            veiculo=plano.veiculo,
                            tipo='licenciamento',
                            vencimento=vencimento,
                            observacao=plano.descricao[:200],
                        )
                        criados += 1
                        self.stdout.write(
                            f'  {plano.veiculo} -> Documento licenciamento '
                            f'(vence {vencimento}).')

                    plano.delete()
                    removidos += 1

                if options['dry_run']:
                    raise _Rollback()
        except _Rollback:
            self.stdout.write(self.style.WARNING('DRY-RUN: nada foi gravado.'))
        else:
            self.stdout.write(self.style.SUCCESS('Correcao concluida.'))

        self.stdout.write(
            f'Planos analisados: {len(planos)} | documentos criados: {criados} '
            f'| ja existentes: {duplicados} | planos removidos: {removidos} '
            f'| sem data (mantidos): {sem_data}')

    def _resolver_organizacao(self, options):
        if options['organizacao']:
            try:
                return Organizacao.objects.get(pk=options['organizacao'])
            except Organizacao.DoesNotExist:
                raise CommandError(
                    f"Organizacao id={options['organizacao']} nao existe.")
        if options['organizacao_nome']:
            try:
                return Organizacao.objects.get(nome=options['organizacao_nome'])
            except Organizacao.DoesNotExist:
                raise CommandError(
                    f"Organizacao \"{options['organizacao_nome']}\" nao existe.")
        return None


class _Rollback(Exception):
    """Sinaliza o rollback do --dry-run."""
