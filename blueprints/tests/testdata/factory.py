import datetime as dt
import urllib.parse
from typing import Generic, TypeVar

import factory
import factory.fuzzy

from django.utils.timezone import now
from eveuniverse.tests.testdata.factories_2 import (
    EveGroupFactory,
    EveSolarSystemFactory,
    EveTypeFactory,
    StationTypeFactory,
)

from app_utils.testdata_factories import EveCharacterFactory, UserMainFactory

from blueprints.constants import EVE_CATEGORY_ID_BLUEPRINT
from blueprints.models import Blueprint, IndustryJob, Location, Owner, Request

T = TypeVar("T")
_BASE_URL = "https://esi.evetech.net/"

faker = factory.faker.faker.Faker()


def make_esi_url(path: str) -> str:
    if path.startswith("/"):
        raise ValueError("path can not start with a slash")
    if path.endswith("/"):
        raise ValueError("path can not end with a slash")

    url = urllib.parse.urljoin(_BASE_URL, path)
    return url


class BaseMetaFactory(Generic[T], factory.base.FactoryMetaClass):
    def __call__(cls, *args, **kwargs) -> T:
        return super().__call__(*args, **kwargs)


class UserMainDefaultFactory(UserMainFactory):
    main_character__scopes = [
        "esi-assets.read_assets.v1",
        "esi-characters.read_blueprints.v1",
        "esi-industry.read_character_jobs.v1",
        "esi-universe.read_structures.v1",
    ]
    permissions__ = [
        "blueprints.basic_access",
        "blueprints.add_personal_blueprint_owner",
    ]


class UserMainCorporationFactory(UserMainFactory):
    main_character__scopes = [
        "esi-assets.read_corporation_assets.v1",
        "esi-corporations.read_blueprints.v1",
        "esi-industry.read_corporation_jobs.v1",
        "esi-universe.read_structures.v1",
    ]
    permissions__ = [
        "blueprints.basic_access",
        "blueprints.add_corporate_blueprint_owner",
    ]


class FrigateBlueprintTypeFactory(EveTypeFactory):
    eve_group = factory.SubFactory(
        EveGroupFactory,
        eve_category__id=EVE_CATEGORY_ID_BLUEPRINT,
        eve_category__name="Blueprint",
        id=105,
        name="Frigate Blueprint",
    )


class LocationStationFactory(
    factory.django.DjangoModelFactory, metaclass=BaseMetaFactory[Location]
):
    class Meta:
        model = Location

    id = factory.Sequence(lambda o: o + 60_000_000)
    name = factory.Faker("city")
    eve_solar_system = factory.SubFactory(EveSolarSystemFactory)
    eve_type = factory.SubFactory(StationTypeFactory)


class LocationItemFactory(
    factory.django.DjangoModelFactory, metaclass=BaseMetaFactory[Location]
):
    class Meta:
        model = Location

    id = factory.Sequence(lambda o: o + 1_008_000_000_000)


class OwnerCharacterFactory(
    factory.django.DjangoModelFactory, metaclass=BaseMetaFactory[Owner]
):
    class Meta:
        model = Owner
        exclude = ("user",)

    user = factory.SubFactory(UserMainDefaultFactory)

    character = factory.LazyAttribute(
        lambda o: o.user.profile.main_character.character_ownership
    )


class OwnerCorporationFactory(
    factory.django.DjangoModelFactory, metaclass=BaseMetaFactory[Owner]
):
    class Meta:
        model = Owner
        exclude = ("user",)

    user = factory.SubFactory(UserMainCorporationFactory)

    corporation = factory.LazyAttribute(
        lambda o: o.user.profile.main_character.corporation
    )
    character = factory.LazyAttribute(
        lambda o: o.user.profile.main_character.character_ownership
    )


class BlueprintFactory(
    factory.django.DjangoModelFactory, metaclass=BaseMetaFactory[Blueprint]
):
    class Meta:
        model = Blueprint

    eve_type = factory.SubFactory(FrigateBlueprintTypeFactory)
    item_id = factory.Sequence(lambda o: o + 1_009_000_000_000)
    location = factory.SubFactory(LocationStationFactory)
    location_flag = Blueprint.LocationFlag.HANGAR
    material_efficiency = 10
    owner = factory.SubFactory(OwnerCharacterFactory)
    quantity = 1
    runs = None
    time_efficiency = 20


class IndustryJobFactory(
    factory.django.DjangoModelFactory, metaclass=BaseMetaFactory[IndustryJob]
):
    class Meta:
        model = IndustryJob

    id = factory.Sequence(lambda o: o + 1_099_000_000_000)
    activity = IndustryJob.Activity.MANUFACTURING
    location = factory.SubFactory(LocationStationFactory)
    blueprint = factory.LazyAttribute(
        lambda o: BlueprintFactory(location=o.location, owner=o.owner)
    )
    installer = factory.SubFactory(EveCharacterFactory)
    owner = factory.SubFactory(OwnerCharacterFactory)
    start_date = factory.fuzzy.FuzzyDateTime(start_dt=now() - dt.timedelta(days=3))
    end_date = factory.fuzzy.FuzzyDateTime(
        start_dt=now(), end_dt=now() + dt.timedelta(days=3)
    )
    runs = 10
    status = "active"


class RequestFactory(
    factory.django.DjangoModelFactory, metaclass=BaseMetaFactory[Request]
):
    class Meta:
        model = Request

    blueprint = factory.SubFactory(BlueprintFactory)
    requesting_user = factory.SubFactory(UserMainDefaultFactory)
    status = Request.STATUS_OPEN
