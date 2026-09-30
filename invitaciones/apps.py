from django.apps import AppConfig


class InvitacionesConfig(AppConfig):
    name = 'invitaciones'

    def ready(self):
        # registra las revisiones propias de "manage.py check --deploy"
        from . import checks  # noqa: F401
