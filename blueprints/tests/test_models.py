import datetime as dt
from http import HTTPStatus
from unittest.mock import patch

import pook

from django.utils.timezone import now
from esi.errors import TokenError, TokenExpiredError
from esi.models import Token

from app_utils.testdata_factories import EveCharacterFactory
from app_utils.testing import NoSocketsTestCase

from blueprints.models import Blueprint, IndustryJob, Owner
from blueprints.tests.helpers import TestCaseWithClearCache
from blueprints.tests.testdata.factory import (
    BlueprintFactory,
    FrigateBlueprintTypeFactory,
    LocationItemFactory,
    LocationStationFactory,
    OwnerCharacterFactory,
    OwnerCorporationFactory,
    make_esi_url,
)

MODELS_PATH = "blueprints.models"


class TestLocationNamePlus(NoSocketsTestCase):
    def test_should_return_name(self):
        # given
        location = LocationStationFactory(name="Alpha")
        # when/then
        self.assertEqual(location.full_qualified_name(), "Alpha")

    def test_should_return_parent_name(self):
        # given
        parent_location = LocationStationFactory(name="Parent")
        location = LocationStationFactory(name="Child", parent=parent_location)
        # when/then
        self.assertEqual(location.full_qualified_name(), "Parent - Child")

    def test_should_return_generic_name(self):
        # given
        location = LocationStationFactory(name="", eve_type=None)
        # when/then
        self.assertEqual(location.full_qualified_name(), f"Location #{location.id}")

    def test_should_return_parent_parent_parent_name(self):
        # given
        parent_location = LocationStationFactory(name="Parent")
        child_location = LocationStationFactory(name="Child 1", parent=parent_location)
        child_child_location = LocationStationFactory(
            name="Child 2", parent=child_location
        )
        location = LocationStationFactory(name="Child 3", parent=child_child_location)
        # when/then
        self.assertEqual(
            location.full_qualified_name(), "Parent - Child 1 - Child 2 - Child 3"
        )


class TestOwner(NoSocketsTestCase):
    def test_should_return_corporation_name_for_owner(self):
        # given
        owner = OwnerCorporationFactory()
        # when
        result = str(owner)
        # then
        self.assertEqual(result, owner.corporation.corporation_name)

    def test_should_return_empty_string_for_empty_owner(self):
        # given
        owner = Owner.objects.create()
        # when
        result = str(owner)
        # then
        self.assertEqual(result, "")


# FIXME: This only works when there are 2 items. Why not with only one?
class TestOwner_UpdateLocationsESI(TestCaseWithClearCache):
    @pook.on
    def test_update_for_corporation(self):
        # given
        owner = OwnerCorporationFactory()
        item_1 = LocationItemFactory()
        item_2 = LocationItemFactory()
        location = LocationStationFactory()
        item_type = FrigateBlueprintTypeFactory()
        pook.get(
            make_esi_url(
                f"corporations/{owner.corporation_strict.corporation_id}/assets"
            ),
            response_headers={"X-Pages": "1"},
            reply=HTTPStatus.OK,
            response_json=[
                {
                    "is_blueprint_copy": False,
                    "is_singleton": True,
                    "item_id": item_1.id,
                    "location_flag": "Hangar",
                    "location_id": location.id,
                    "location_type": "station",
                    "quantity": 1,
                    "type_id": item_type.id,
                },
                {
                    "is_blueprint_copy": True,
                    "is_singleton": False,
                    "item_id": item_2.id,
                    "location_flag": "Hangar",
                    "location_id": item_1.id,
                    "location_type": "item",
                    "quantity": 3,
                    "type_id": item_type.id,
                },
            ],
        )

        # when
        owner.update_locations_esi()

        # then
        item_1.refresh_from_db()
        self.assertEqual(item_1.parent, location)
        self.assertEqual(item_1.eve_type, item_type)

    @pook.on
    def test_update_for_character(self):
        # given
        owner = OwnerCharacterFactory()
        item_1 = LocationItemFactory()
        item_2 = LocationItemFactory()
        location = LocationStationFactory()
        item_type = FrigateBlueprintTypeFactory()
        pook.get(
            make_esi_url(
                f"characters/{owner.eve_character_strict.character_id}/assets"
            ),
            response_headers={"X-Pages": "1"},
            reply=HTTPStatus.OK,
            response_json=[
                {
                    "is_blueprint_copy": False,
                    "is_singleton": True,
                    "item_id": item_1.id,
                    "location_flag": "Hangar",
                    "location_id": location.id,
                    "location_type": "station",
                    "quantity": 1,
                    "type_id": item_type.id,
                },
                {
                    "is_blueprint_copy": True,
                    "is_singleton": False,
                    "item_id": item_2.id,
                    "location_flag": "Hangar",
                    "location_id": item_1.id,
                    "location_type": "item",
                    "quantity": 3,
                    "type_id": item_type.id,
                },
            ],
        )

        # when
        owner.update_locations_esi()

        # then
        item_1.refresh_from_db()
        self.assertEqual(item_1.parent, location)
        self.assertEqual(item_1.eve_type, item_type)


class TestOwner_UpdateBlueprintsESI(TestCaseWithClearCache):
    @pook.on
    def test_update_for_corporation(self):
        # given
        owner = OwnerCorporationFactory()
        location = LocationStationFactory()
        item_type = FrigateBlueprintTypeFactory()
        item_id = 1_008_000_000_001
        quantity = 3
        material_efficiency = 0
        time_efficiency = 0
        runs = 100
        pook.get(
            make_esi_url(
                f"corporations/{owner.corporation_strict.corporation_id}/blueprints"
            ),
            response_headers={"X-Pages": "1"},
            reply=HTTPStatus.OK,
            response_json=[
                {
                    "item_id": item_id,
                    "location_flag": "Hangar",
                    "location_id": location.id,
                    "material_efficiency": material_efficiency,
                    "quantity": quantity,
                    "runs": runs,
                    "time_efficiency": time_efficiency,
                    "type_id": item_type.id,
                },
            ],
        )

        # when
        owner.update_blueprints_esi()

        # then
        self.assertEqual(owner.blueprints.count(), 1)
        obj: Blueprint = owner.blueprints.first()
        self.assertEqual(obj.item_id, item_id)
        self.assertEqual(obj.eve_type, item_type)
        self.assertEqual(obj.location_flag, Blueprint.LocationFlag.HANGAR)
        self.assertEqual(obj.location, location)
        self.assertEqual(obj.material_efficiency, material_efficiency)
        self.assertEqual(obj.quantity, quantity)
        self.assertEqual(obj.runs, runs)
        self.assertEqual(obj.time_efficiency, time_efficiency)

    @pook.on
    def test_update_for_character(self):
        # given
        owner = OwnerCharacterFactory()
        location = LocationStationFactory()
        item_type = FrigateBlueprintTypeFactory()
        item_id = 1_008_000_000_001
        quantity = 3
        material_efficiency = 0
        time_efficiency = 0
        runs = 100
        pook.get(
            make_esi_url(
                f"characters/{owner.eve_character_strict.character_id}/blueprints"
            ),
            response_headers={"X-Pages": "1"},
            reply=HTTPStatus.OK,
            response_json=[
                {
                    "item_id": item_id,
                    "location_flag": "Hangar",
                    "location_id": location.id,
                    "material_efficiency": material_efficiency,
                    "quantity": quantity,
                    "runs": runs,
                    "time_efficiency": time_efficiency,
                    "type_id": item_type.id,
                },
            ],
        )

        # when
        owner.update_blueprints_esi()

        # then
        self.assertEqual(owner.blueprints.count(), 1)
        obj: Blueprint = owner.blueprints.first()
        self.assertEqual(obj.item_id, item_id)
        self.assertEqual(obj.eve_type, item_type)
        self.assertEqual(obj.location_flag, Blueprint.LocationFlag.HANGAR)
        self.assertEqual(obj.location, location)
        self.assertEqual(obj.material_efficiency, material_efficiency)
        self.assertEqual(obj.quantity, quantity)
        self.assertEqual(obj.runs, runs)
        self.assertEqual(obj.time_efficiency, time_efficiency)


class TestOwner_UpdateIndustryJobsEsi(TestCaseWithClearCache):
    @pook.on
    def test_should_update_for_corporation(self):
        # given
        owner = OwnerCorporationFactory()
        bp = BlueprintFactory(owner=owner)
        end_date = now() + dt.timedelta(hours=3)
        installer = EveCharacterFactory()
        job_id = 42
        location = LocationStationFactory()
        runs = 100
        start_date = now()
        status = "active"
        duration = int((end_date - start_date).total_seconds())
        pook.get(
            make_esi_url(
                f"corporations/{owner.corporation_strict.corporation_id}/industry/jobs"
            ),
            response_headers={"X-Pages": "1"},
            reply=HTTPStatus.OK,
            response_json=[
                {
                    "activity_id": 1,
                    "blueprint_id": bp.item_id,
                    "blueprint_location_id": bp.location.id,
                    "blueprint_type_id": bp.eve_type.id,
                    "duration": duration,
                    "end_date": end_date.isoformat(),
                    "facility_id": location.id,
                    "installer_id": installer.character_id,
                    "job_id": job_id,
                    "location_id": location.id,
                    "output_location_id": location.id,
                    "runs": runs,
                    "start_date": start_date.isoformat(),
                    "status": status,
                }
            ],
        )

        # when
        owner.update_industry_jobs_esi()

        # then
        self.assertEqual(owner.jobs.count(), 1)
        obj: IndustryJob = owner.jobs.first()
        self.assertEqual(obj.id, job_id)
        self.assertEqual(obj.activity, IndustryJob.Activity.MANUFACTURING)
        self.assertEqual(obj.blueprint, bp)
        self.assertEqual(obj.location, location)
        self.assertEqual(obj.installer, installer)
        self.assertEqual(obj.runs, runs)
        self.assertEqual(obj.start_date, start_date)
        self.assertEqual(obj.end_date, end_date)
        self.assertEqual(obj.status, status)

    @pook.on
    def test_should_update_for_character(self):
        # given
        owner = OwnerCharacterFactory()
        bp = BlueprintFactory(owner=owner)
        end_date = now() + dt.timedelta(hours=3)
        installer = EveCharacterFactory()
        job_id = 42
        location = LocationStationFactory()
        runs = 100
        start_date = now()
        status = "active"
        duration = int((end_date - start_date).total_seconds())
        pook.get(
            make_esi_url(
                f"characters/{owner.eve_character_strict.character_id}/industry/jobs"
            ),
            response_headers={"X-Pages": "1"},
            reply=HTTPStatus.OK,
            response_json=[
                {
                    "activity_id": 1,
                    "blueprint_id": bp.item_id,
                    "blueprint_location_id": bp.location.id,
                    "blueprint_type_id": bp.eve_type.id,
                    "duration": duration,
                    "end_date": end_date.isoformat(),
                    "facility_id": location.id,
                    "installer_id": installer.character_id,
                    "job_id": job_id,
                    "output_location_id": location.id,
                    "runs": runs,
                    "start_date": start_date.isoformat(),
                    "station_id": location.id,
                    "status": status,
                }
            ],
        )

        # when
        owner.update_industry_jobs_esi()

        # then
        self.assertEqual(owner.jobs.count(), 1)
        obj: IndustryJob = owner.jobs.first()
        self.assertEqual(obj.id, job_id)
        self.assertEqual(obj.activity, IndustryJob.Activity.MANUFACTURING)
        self.assertEqual(obj.blueprint, bp)
        self.assertEqual(obj.location, location)
        self.assertEqual(obj.installer, installer)
        self.assertEqual(obj.runs, runs)
        self.assertEqual(obj.start_date, start_date)
        self.assertEqual(obj.end_date, end_date)
        self.assertEqual(obj.status, status)


class TestOwner_ValidToken(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.owner = OwnerCharacterFactory()

    def test_should_return_valid_token(self):
        # when
        result = self.owner.valid_token(["esi-characters.read_blueprints.v1"])
        # then
        self.assertIsInstance(result, Token)

    def test_should_raise_error_when_no_token_with_requested_scope_found(self):
        # when/then
        with self.assertRaises(TokenError):
            self.owner.valid_token(["unknown-scope"])

    @patch(MODELS_PATH + ".Token.objects.filter")
    def test_should_raise_error_when_token_has_issue(self, mock):
        # given
        mock.side_effect = TokenExpiredError
        # when/then
        with self.assertRaises(TokenExpiredError):
            self.owner.valid_token(["esi-characters.read_blueprints.v1"])
