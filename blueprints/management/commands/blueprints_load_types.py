import logging

from django.core.management import call_command
from django.core.management.base import BaseCommand

from blueprints import __title__
from blueprints.constants import EVE_CATEGORY_ID_BLUEPRINT

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Preloads data required for aa-blueprints from ESI"

    def handle(self, *args, **options):
        call_command(
            "eveuniverse_load_types",
            __title__,
            "--category_id",
            str(EVE_CATEGORY_ID_BLUEPRINT),
        )
