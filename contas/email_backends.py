"""Backend de e-mail que envia pela API HTTP do Brevo (HTTPS/443).

Usado em produção quando o SMTP (porta 587/465/2525) e bloqueado pelo provedor
de hospedagem. Ativado definindo a variavel de ambiente BREVO_API_KEY.
"""
import json
import urllib.request
from email.utils import parseaddr
from urllib.error import HTTPError, URLError

from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend


class BrevoAPIBackend(BaseEmailBackend):
    api_url = 'https://api.brevo.com/v3/smtp/email'

    def __init__(self, fail_silently=False, **kwargs):
        super().__init__(fail_silently=fail_silently, **kwargs)
        self.api_key = getattr(settings, 'BREVO_API_KEY', '')

    def send_messages(self, email_messages):
        if not email_messages:
            return 0
        if not self.api_key:
            if not self.fail_silently:
                raise ValueError('BREVO_API_KEY não configurada.')
            return 0
        enviados = 0
        for msg in email_messages:
            try:
                self._enviar(msg)
                enviados += 1
            except Exception:
                if not self.fail_silently:
                    raise
        return enviados

    def _remetente(self, from_email):
        nome, endereco = parseaddr(from_email or settings.DEFAULT_FROM_EMAIL)
        return {'name': nome or endereco, 'email': endereco}

    def _enviar(self, msg):
        destinatarios = [{'email': e} for e in msg.to]
        if not destinatarios:
            return
        payload = {
            'sender': self._remetente(msg.from_email),
            'to': destinatarios,
            'subject': msg.subject,
            'textContent': msg.body or ' ',
        }
        if msg.cc:
            payload['cc'] = [{'email': e} for e in msg.cc]
        if msg.bcc:
            payload['bcc'] = [{'email': e} for e in msg.bcc]
        reply_to = (msg.reply_to or [None])[0]
        if reply_to:
            nome, endereco = parseaddr(reply_to)
            payload['replyTo'] = {'email': endereco, 'name': nome or endereco}
        # Versao HTML, se houver (EmailMultiAlternatives).
        for conteudo, mimetype in getattr(msg, 'alternatives', None) or []:
            if mimetype == 'text/html':
                payload['htmlContent'] = conteudo

        req = urllib.request.Request(
            self.api_url, data=json.dumps(payload).encode('utf-8'), method='POST')
        req.add_header('api-key', self.api_key)
        req.add_header('content-type', 'application/json')
        req.add_header('accept', 'application/json')
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                resp.read()
        except HTTPError as exc:
            corpo = exc.read().decode('utf-8', 'replace')
            raise RuntimeError(f'Brevo API {exc.code}: {corpo}') from exc
        except URLError as exc:
            raise RuntimeError(f'Falha de conexão com a API do Brevo: {exc.reason}') from exc
