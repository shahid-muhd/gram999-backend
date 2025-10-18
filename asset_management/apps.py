from django.apps import AppConfig
import logging

logger = logging.getLogger(__name__)

class AssetManagementConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'asset_management'

