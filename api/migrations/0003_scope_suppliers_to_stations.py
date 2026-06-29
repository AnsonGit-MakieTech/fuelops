import django.db.models.deletion
from django.db import migrations, models


def scope_suppliers_to_stations(apps, schema_editor):
    FuelDelivery = apps.get_model("api", "FuelDelivery")
    Station = apps.get_model("api", "Station")
    Supplier = apps.get_model("api", "Supplier")
    fallback_station = Station.objects.order_by("id").first()

    for supplier in Supplier.objects.all().order_by("id"):
        station_ids = list(
            FuelDelivery.objects.filter(supplier=supplier)
            .values_list("station_id", flat=True)
            .distinct()
            .order_by("station_id")
        )

        if not station_ids:
            if fallback_station:
                supplier.station_id = fallback_station.id
                supplier.save(update_fields=["station"])
            else:
                supplier.delete()
            continue

        supplier.station_id = station_ids[0]
        supplier.save(update_fields=["station"])

        for station_id in station_ids[1:]:
            station_supplier = Supplier.objects.create(
                station_id=station_id,
                name=supplier.name,
                contact_person=supplier.contact_person,
                phone=supplier.phone,
                email=supplier.email,
                address=supplier.address,
                is_active=supplier.is_active,
            )
            FuelDelivery.objects.filter(
                supplier=supplier,
                station_id=station_id,
            ).update(supplier=station_supplier)


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0002_stationinvitation_stationmembership"),
    ]

    operations = [
        migrations.AddField(
            model_name="supplier",
            name="station",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="suppliers",
                to="api.station",
            ),
        ),
        migrations.AlterField(
            model_name="supplier",
            name="name",
            field=models.CharField(max_length=150),
        ),
        migrations.AlterModelOptions(
            name="supplier",
            options={"ordering": ["station__name", "name"]},
        ),
        migrations.RunPython(scope_suppliers_to_stations, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="supplier",
            name="station",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="suppliers",
                to="api.station",
            ),
        ),
        migrations.AddConstraint(
            model_name="supplier",
            constraint=models.UniqueConstraint(
                fields=("station", "name"),
                name="unique_supplier_name_per_station",
            ),
        ),
    ]
