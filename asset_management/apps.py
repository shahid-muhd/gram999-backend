from django.apps import AppConfig

class AssetManagementConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'asset_management'

    def ready(self):
        from asset_management.tasks import fetch_gold_price_and_broadcast
        from gram999_backend.scheduler import scheduler

        if not scheduler.get_jobs():
            scheduler.add_job(fetch_gold_price_and_broadcast, 'interval', minutes=2)
            scheduler.start()
