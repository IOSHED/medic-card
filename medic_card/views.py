from django.shortcuts import render


def home(request):
    return render(request, "medic_card/home.html")
