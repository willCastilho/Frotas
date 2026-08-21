from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = ('Envia um e-mail de teste para validar a configuracao de SMTP. '
            'Uso: python manage.py enviar_email_teste destino@exemplo.com')

    def add_arguments(self, parser):
        parser.add_argument('destino', help='E-mail que recebera a mensagem de teste.')

    def handle(self, *args, **options):
        destino = options['destino']
        backend = getattr(settings, 'EMAIL_BACKEND', '')
        self.stdout.write(f'Backend de e-mail: {backend}')
        if 'brevo' in backend.lower():
            self.stdout.write('Modo: API HTTP do Brevo (HTTPS/443).')
        elif 'smtp' in backend.lower():
            self.stdout.write(
                f'SMTP: {settings.EMAIL_HOST}:{settings.EMAIL_PORT} '
                f'(TLS={getattr(settings, "EMAIL_USE_TLS", False)}, '
                f'SSL={getattr(settings, "EMAIL_USE_SSL", False)})')
        else:
            self.stdout.write(self.style.WARNING(
                'Nenhum e-mail configurado (BREVO_API_KEY/EMAIL_HOST vazios). O '
                'e-mail iria para o console. Defina as variaveis no ambiente.'))

        try:
            enviados = send_mail(
                subject='[Gestão de Frotas] E-mail de teste',
                message=('Este é um e-mail de teste do Gestão de Frotas.\n\n'
                         'Se você recebeu esta mensagem, o envio de e-mail está '
                         'funcionando corretamente.'),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[destino],
                fail_silently=False,
            )
        except Exception as exc:
            raise CommandError(f'Falha ao enviar: {exc}')

        if enviados:
            self.stdout.write(self.style.SUCCESS(
                f'E-mail de teste enviado para {destino}. '
                f'De: {settings.DEFAULT_FROM_EMAIL}'))
        else:
            self.stdout.write(self.style.ERROR('Nenhum e-mail foi enviado.'))
