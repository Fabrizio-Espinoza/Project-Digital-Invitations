from django.urls import path
from . import views

app_name = "invitaciones"

urlpatterns = [
    path("sw.js", views.service_worker, name="service_worker"),
    path("<slug:slug>/", views.detalle_invitacion, name="detalle"),
    path("<slug:slug>/rsvp/", views.enviar_confirmacion, name="rsvp"),
    path("<slug:slug>/manifest.webmanifest", views.manifest_invitacion, name="manifest"),
    path("<slug:slug>/rsvp/conteo/", views.conteo_confirmados, name="conteo"),
    path("<slug:slug>/votar/", views.enviar_voto, name="votar"),
    path("<slug:slug>/votar/conteo/", views.conteo_votos, name="conteo_votos"),
    path("<slug:slug>/calendario.ics", views.calendario_ics, name="calendario"),
]
