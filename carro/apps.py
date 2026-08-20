from django.apps import AppConfig


class CarroConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'carro'

    def ready(self):
        # Registra os modelos na auditoria (django-auditlog)
        from auditlog.registry import auditlog

        from .models import (
            Abastecimento,
            Custo,
            PlanoManutencao,
            RegistroQuilometragem,
            Veiculo,
        )

        for modelo in (Veiculo, Custo, Abastecimento,
                       RegistroQuilometragem, PlanoManutencao):
            auditlog.register(modelo)
