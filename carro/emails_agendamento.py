"""Notificacoes por e-mail do modulo de pre-agendamento.

Todas usam fail_silently=True: a notificacao nunca deve quebrar o fluxo (o
estado do agendamento ja fica registrado no sistema e visivel na tela).
"""
from django.conf import settings
from django.core.mail import send_mail

from contas.models import PerfilUsuario


def _emails_gestores(organizacao):
    return list(
        PerfilUsuario.objects.filter(
            organizacao=organizacao,
            papel__in=[PerfilUsuario.PAPEL_ADMIN, PerfilUsuario.PAPEL_GESTOR])
        .exclude(user__email='')
        .values_list('user__email', flat=True)
    )


def _periodo(sol):
    return (f'{sol.saida_prevista:%d/%m/%Y %H:%M} a '
            f'{sol.retorno_previsto:%d/%m/%Y %H:%M}')


def notificar_gestores_nova_solicitacao(sol):
    """Avisa os gestores que ha uma nova solicitacao para aprovar."""
    emails = _emails_gestores(sol.organizacao)
    if not emails:
        return
    corpo = (
        f'Nova solicitação de veículo — {sol.organizacao.nome}\n\n'
        f'Solicitante: {sol.solicitante.nome} ({sol.setor})\n'
        f'Período: {_periodo(sol)}\n'
        f'Destino: {sol.destino}\n'
        f'Precisa de motorista: {"Sim" if sol.precisa_motorista else "Não"}\n\n'
        'Acesse o sistema para aprovar ou recusar.'
    )
    send_mail(
        subject=f'[Gestão de Frotas] Nova solicitação de veículo — {sol.solicitante.nome}',
        message=corpo, from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=emails, fail_silently=True)


def notificar_decisao(sol):
    """Avisa o solicitante que sua solicitacao foi aprovada ou recusada."""
    email = sol.solicitante.email or getattr(sol.solicitante.user, 'email', '')
    if not email:
        return
    if sol.status == sol.STATUS_APROVADA:
        motorista = sol.motorista.nome if sol.motorista else 'você dirige'
        corpo = (
            f'Sua solicitação de veículo foi APROVADA.\n\n'
            f'Veículo: {sol.veiculo}\n'
            f'Período: {_periodo(sol)}\n'
            f'Destino: {sol.destino}\n'
            f'Motorista: {motorista}\n\n'
            'Lembre-se de registrar a devolução (com o KM final) ao retornar.'
        )
        assunto = 'Solicitação de veículo aprovada'
    else:
        motivo = f'\nMotivo: {sol.motivo_recusa}' if sol.motivo_recusa else ''
        corpo = (
            f'Sua solicitação de veículo foi RECUSADA.\n\n'
            f'Período: {_periodo(sol)}\n'
            f'Destino: {sol.destino}{motivo}\n\n'
            'Você pode fazer uma nova solicitação pelo sistema.'
        )
        assunto = 'Solicitação de veículo recusada'
    send_mail(
        subject=f'[Gestão de Frotas] {assunto}',
        message=corpo, from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[email], fail_silently=True)


def notificar_lembrete_devolucao(sol):
    """Lembra o solicitante de registrar a devolucao pendente."""
    email = sol.solicitante.email or getattr(sol.solicitante.user, 'email', '')
    if not email:
        return
    corpo = (
        f'Lembrete: você tem um veículo a devolver.\n\n'
        f'Veículo: {sol.veiculo}\n'
        f'Retorno previsto: {sol.retorno_previsto:%d/%m/%Y %H:%M}\n'
        f'Destino: {sol.destino}\n\n'
        'Registre a devolução (com o KM final) no sistema. Enquanto ela '
        'estiver pendente, você não poderá solicitar outro veículo.'
    )
    send_mail(
        subject='[Gestão de Frotas] Devolução de veículo pendente',
        message=corpo, from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[email], fail_silently=True)
