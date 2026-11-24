from django.urls import path

from . import views

app_name = "expenses"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("expenses/", views.expense_list, name="list"),
    path("expenses/new/", views.expense_create, name="create"),
    path("expenses/export.csv", views.export_csv, name="export"),
    path("expenses/<int:pk>/edit/", views.expense_update, name="update"),
    path("expenses/<int:pk>/delete/", views.expense_delete, name="delete"),
]
