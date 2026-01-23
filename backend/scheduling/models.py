from django.db import models

class Patient(models.Model):
    name = models.CharField(max_length=100)
    status = models.CharField(max_length=20)

    class Meta:
        db_table = "scheduling_patient"

    def __str__(self):
        return self.name
