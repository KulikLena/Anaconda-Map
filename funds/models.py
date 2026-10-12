from django.db import models


class Country(models.Model):
    code = models.CharField(max_length=2, primary_key=True)  # ISO 3166-1 alpha-2 (GR, not EL)
    name = models.CharField(max_length=100)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "countries"

    def __str__(self):
        return f"{self.name} ({self.code})"


class Observation(models.Model):
    """One country, one year: real estate fund total assets vs GDP."""

    country = models.ForeignKey(Country, on_delete=models.CASCADE, related_name="observations")
    year = models.PositiveSmallIntegerField()
    period = models.CharField(max_length=7, help_text="Quarter the asset value is taken from, e.g. 2025-Q4")
    assets_meur = models.FloatField(help_text="Real estate fund total assets, EUR million (ECB IVF)")
    gdp_meur = models.FloatField(null=True, blank=True, help_text="GDP at current prices, EUR million (Eurostat)")
    gdp_year = models.PositiveSmallIntegerField(null=True, blank=True, help_text="Year the GDP figure refers to")
    share_pct = models.FloatField(null=True, blank=True, help_text="assets / GDP x 100")

    class Meta:
        ordering = ["country", "year"]
        constraints = [models.UniqueConstraint(fields=["country", "year"], name="unique_country_year")]

    @property
    def is_partial(self):
        """True when the year is not complete (latest quarter is not Q4)."""
        return not self.period.endswith("Q4")

    def __str__(self):
        return f"{self.country_id} {self.year}: {self.share_pct}"
