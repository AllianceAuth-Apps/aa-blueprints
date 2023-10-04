"""Tasks for Blueprints."""

import random

from bravado.exception import HTTPBadGateway, HTTPGatewayTimeout, HTTPServiceUnavailable
from celery import shared_task

from esi.models import Token

from allianceauth.services.hooks import get_extension_logger
from allianceauth.services.tasks import QueueOnce
from app_utils.esi import EsiErrorLimitExceeded, EsiOffline
from app_utils.logging import LoggerAddTag

from . import __title__
from .app_settings import BLUEPRINTS_TASKS_TIME_LIMIT
from .models import Location, Owner

DEFAULT_TASK_PRIORITY = 6


logger = LoggerAddTag(get_extension_logger(__name__), __title__)

TASK_DEFAULT_KWARGS = {
    "time_limit": BLUEPRINTS_TASKS_TIME_LIMIT,
}

TASK_ESI_KWARGS = {
    **TASK_DEFAULT_KWARGS,
    **{
        "bind": True,
        "autoretry_for": (
            OSError,
            HTTPBadGateway,
            HTTPGatewayTimeout,
            HTTPServiceUnavailable,
        ),
        "retry_kwargs": {"max_retries": 3},
        "retry_backoff": 30,
    },
}


@shared_task(
    **{
        **TASK_ESI_KWARGS,
        **{
            "base": QueueOnce,
            "once": {"keys": ["owner_pk"], "graceful": True},
            "max_retries": None,
        },
    }
)
def update_blueprints_for_owner(self, owner_pk):
    """fetches all blueprints for owner from ESI"""
    owner = Owner.objects.get(pk=owner_pk)
    owner.update_blueprints_esi()


@shared_task(
    **{
        **TASK_ESI_KWARGS,
        **{
            "base": QueueOnce,
            "once": {"keys": ["owner_pk"], "graceful": True},
            "max_retries": None,
        },
    }
)
def update_industry_jobs_for_owner(self, owner_pk):
    """fetches all industry jobs for owner from ESI"""
    owner = Owner.objects.get(pk=owner_pk)
    owner.update_industry_jobs_esi()


@shared_task(
    **{
        **TASK_ESI_KWARGS,
        **{
            "base": QueueOnce,
            "once": {"keys": ["owner_pk"], "graceful": True},
            "max_retries": None,
        },
    }
)
def update_locations_for_owner(self, owner_pk: int):
    """fetches all blueprints for owner from ESI"""
    owner = Owner.objects.get(pk=owner_pk)
    owner.update_locations_esi()


@shared_task(**TASK_DEFAULT_KWARGS)
def update_all_blueprints():
    for owner in Owner.objects.filter(is_active=True):
        update_blueprints_for_owner.apply_async(
            kwargs={"owner_pk": owner.pk}, priority=DEFAULT_TASK_PRIORITY
        )


@shared_task(**TASK_DEFAULT_KWARGS)
def update_all_industry_jobs():
    for owner in Owner.objects.filter(is_active=True):
        update_industry_jobs_for_owner.apply_async(
            kwargs={"owner_pk": owner.pk}, priority=DEFAULT_TASK_PRIORITY
        )


@shared_task(**TASK_DEFAULT_KWARGS)
def update_all_locations():
    for owner in Owner.objects.filter(is_active=True):
        update_locations_for_owner.apply_async(
            kwargs={"owner_pk": owner.pk}, priority=DEFAULT_TASK_PRIORITY
        )


@shared_task(
    **{
        **TASK_ESI_KWARGS,
        **{
            "base": QueueOnce,
            "once": {"keys": ["id"], "graceful": True},
            "max_retries": None,
        },
    }
)
def update_structure_esi(self, id: int, token_pk: int):
    """Updates a structure object from ESI
    and retries later if the ESI error limit has already been reached
    """
    try:
        token = Token.objects.get(pk=token_pk)
    except Token.DoesNotExist as ex:
        raise Token.DoesNotExist(
            f"Location #{id}: Requested token with pk {token_pk} does not exist"
        ) from ex

    try:
        Location.objects.structure_update_or_create_esi(id, token)
    except EsiOffline as ex:
        logger.warning(
            "Location #%s: ESI appears to be offline. Trying again in 30 minutes.", id
        )
        raise self.retry(countdown=30 * 60 + int(random.uniform(1, 20))) from ex
    except EsiErrorLimitExceeded as ex:
        logger.warning(
            "Location #%s: ESI error limit threshold reached. "
            "Trying again in %s seconds",
            id,
            ex.retry_in,
        )
        raise self.retry(countdown=ex.retry_in) from ex
