from django.contrib import admin

from .models import Country, Observation


@admin.register(Country)
class CountryAdmin(admin.ModelAdmin):
    list_display = ("code", "name")


@admin.register(Observation)
class ObservationAdmin(admin.ModelAdmin):
    list_display = ("country", "year", "period", "assets_meur", "gdp_meur", "gdp_year", "share_pct")
    list_filter = ("country", "year")
