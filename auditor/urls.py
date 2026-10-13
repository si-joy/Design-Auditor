from django.urls import path

from . import views


app_name = "auditor"


urlpatterns = [
    path(
        "",
        views.home,
        name="home",
    ),

    path(
        "run/",
        views.run_audit,
        name="run_audit",
    ),
]