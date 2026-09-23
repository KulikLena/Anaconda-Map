from django.db import models

from django.db import models

class Project(models.Model):
    name = models.CharField(max_length=200)
    developer = models.CharField(max_length=200, blank=True)
    status = models.CharField(max_length=50, blank=True)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)

    def __str__(self):
        return self.name
