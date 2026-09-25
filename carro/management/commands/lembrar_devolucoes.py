"""Envia lembretes de devolucao pendente aos solicitantes.

Uma devolucao esta pendente quando o veiculo esta em uso ou quando a reserva
aprovada ja passou do retorno previsto sem devolucao registrada. Ideal para
rodar via cron (ex.: diariamente), como o comando enviar_alertas.
"""
from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils import timezone

from carro.emails_agendamento import notificar_lembrete_devolucao
from carro.models import SolicitacaoVeiculo


class Command(BaseCommand):
    help = ('Envia por e-mail lembretes de devolucao pendente aos '
            'solicitantes (veiculo em uso ou retorno previsto vencido).')

    def handle(self, *args, **options):
        agora = timezone.now()
        pendentes = (SolicitacaoVeiculo.objects
                     .filter(
                         Q(status=SolicitacaoVeiculo.STATUS_EM_USO)
                         | Q(status=SolicitacaoVeiculo.STATUS_APROVADA,
                             retorno_previsto__lte=agora))
                     .select_related('solicitante', 'solicitante__user', 'veiculo'))

        enviados = 0
        for sol in pendentes:
            notificar_lembrete_devolucao(sol)
            enviados += 1
            self.stdout.write(
                f'{sol.solicitante.nome}: {sol.veiculo} '
                f'(retorno {sol.retorno_previsto:%d/%m/%Y %H:%M})')

        self.stdout.write(self.style.SUCCESS(
            f'Concluido. {enviados} lembrete(s) de devolução enviados.'))
