from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand

from carro.models import PlanoManutencao, Veiculo
from contas.models import Organizacao, PerfilUsuario


class Command(BaseCommand):
    help = ('Envia por e-mail os alertas de manutencao atrasada e de orcamento '
            'estourado para os administradores de cada organizacao. '
            'Ideal para rodar via cron (ex.: diariamente).')

    def handle(self, *args, **options):
        total = 0
        for org in Organizacao.objects.all():
            linhas = self._alertas_da_org(org)
            if not linhas:
                continue
            emails = list(
                PerfilUsuario.objects.filter(
                    organizacao=org, papel__in=[PerfilUsuario.PAPEL_ADMIN,
                                                PerfilUsuario.PAPEL_GESTOR])
                .exclude(user__email='')
                .values_list('user__email', flat=True)
            )
            if not emails:
                continue
            corpo = (
                f'Alertas da frota — {org.nome}\n\n' + '\n'.join(linhas) +
                '\n\nAcesse o sistema para mais detalhes.'
            )
            send_mail(
                subject=f'[Gestão de Frotas] Alertas — {org.nome}',
                message=corpo,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=emails,
                fail_silently=True,
            )
            total += 1
            self.stdout.write(f'{org.nome}: {len(linhas)} alerta(s) -> {len(emails)} e-mail(s)')

        self.stdout.write(self.style.SUCCESS(f'Concluido. {total} organizacao(oes) notificada(s).'))

    def _alertas_da_org(self, org):
        linhas = []
        # Manutencoes atrasadas / proximas
        for plano in PlanoManutencao.objects.filter(
                veiculo__organizacao=org).select_related('veiculo'):
            st = plano.status(plano.veiculo.km_atual())
            if st['cor'] == 'red':
                linhas.append(f'🔴 {plano.veiculo}: {plano.descricao} — {st["detalhe"]}')
        # Orcamento estourado no mes
        for v in Veiculo.objects.filter(organizacao=org, meta_custo_mensal__isnull=False):
            info = v.custo_vs_meta()
            if info and info['cor'] == 'red':
                linhas.append(f'💸 {v}: custo em {info["pct"]}% da meta')
        return linhas
