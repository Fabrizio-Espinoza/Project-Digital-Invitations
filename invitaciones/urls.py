from django.urls import path
from . import views

app_name = "invitaciones"

urlpatterns = [
    path("<slug:slug>/", views.detalle_invitacion, name="detalle"),
    path("<slug:slug>/rsvp/", views.enviar_confirmacion, name="rsvp"),
    path("<slug:slug>/rsvp/conteo/", views.conteo_confirmados, name="conteo"),
    path("<slug:slug>/votar/", views.enviar_voto, name="votar"),
    path("<slug:slug>/votar/conteo/", views.conteo_votos, name="conteo_votos"),
    path("<slug:slug>/calendario.ics", views.calendario_ics, name="calendario"),
]
