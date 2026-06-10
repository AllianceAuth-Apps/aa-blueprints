import datetime as dt
from http import HTTPStatus
from unittest.mock import patch

import pook

from django.utils.timezone import now
from esi.errors import TokenError, TokenExpiredError
from esi.models import Token
from eveuniverse.models import EveType

from allianceauth.eveonline.models import EveCharacter
from allianceauth.tests.auth_utils import AuthUtils
from app_utils.testdata_factories import EveCharacterFactory
from app_utils.testing import NoSocketsTestCase

from blueprints.models import Blueprint, IndustryJob, Location, Owner, Request
from blueprints.tests import (
    add_character_to_user,
    create_owner,
    create_user_from_evecharacter,
)
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
from blueprints.tests.testdata.load_entities import load_entities
from blueprints.tests.testdata.load_eveuniverse import load_eveuniverse
from blueprints.tests.testdata.load_locations import load_locations

MODELS_PATH = "blueprints.models"


class TestBlueprintsBase(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        load_entities()
        load_eveuniverse()
        load_locations()


class TestBlueprintQuerySet(TestBlueprintsBase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        # given
        cls.owner_1001 = create_owner(character_id=1001, corporation_id=None)
        Blueprint.objects.create(
            location=Location.objects.get(id=60003760),
            eve_type=EveType.objects.get(id=33519),
            owner=cls.owner_1001,
            runs=10,
            location_flag="AssetSafety",
            material_efficiency=10,
            time_efficiency=30,
            item_id=1,
        )
        cls.owner_1002 = create_owner(character_id=1002, corporation_id=2001)
        Blueprint.objects.create(
            location=Location.objects.get(id=1000000000001),
            eve_type=EveType.objects.get(id=33519),
            owner=cls.owner_1002,
            location_flag="AssetSafety",
            material_efficiency=20,
            time_efficiency=40,
            item_id=2,
        )

    def test_should_annotate_is_bpo(self):
        # when
        result = Blueprint.objects.all().annotate_is_bpo().values()
        # then
        obj = result[0]
        self.assertEqual(obj["item_id"], 1)
        self.assertEqual(obj["is_bpo"], "no")
        obj = result[1]
        self.assertEqual(obj["item_id"], 2)
        self.assertEqual(obj["is_bpo"], "yes")

    def test_should_annotate_owner_name(self):
        # when
        result = Blueprint.objects.all().annotate_owner_name().values()
        # then
        obj = result[0]
        self.assertEqual(obj["item_id"], 1)
        self.assertEqual(obj["owner_name"], "Bruce Wayne")
        obj = result[1]
        self.assertEqual(obj["item_id"], 2)
        self.assertEqual(obj["owner_name"], "Wayne Technologies")


class TestBlueprintManagerUserHasAccess(TestBlueprintsBase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        # given
        cls.owner_1002 = create_owner(character_id=1002, corporation_id=2001)
        Blueprint.objects.create(
            location=Location.objects.get(id=60003760),
            eve_type=EveType.objects.get(id=33519),
            owner=cls.owner_1002,
            location_flag="AssetSafety",
            material_efficiency=10,
            time_efficiency=30,
            item_id=2,
        )
        cls.owner_1003 = create_owner(character_id=1003, corporation_id=2002)
        Blueprint.objects.create(
            location=Location.objects.get(id=60003760),
            eve_type=EveType.objects.get(id=33519),
            owner=cls.owner_1003,
            location_flag="AssetSafety",
            material_efficiency=10,
            time_efficiency=30,
            item_id=3,
        )
        cls.owner_1101 = create_owner(character_id=1101, corporation_id=2101)
        Blueprint.objects.create(
            location=Location.objects.get(id=60003760),
            eve_type=EveType.objects.get(id=33519),
            owner=cls.owner_1101,
            location_flag="AssetSafety",
            material_efficiency=10,
            time_efficiency=30,
            item_id=4,
        )
        cls.owner_1102 = create_owner(character_id=1102, corporation_id=2102)
        Blueprint.objects.create(
            location=Location.objects.get(id=60003760),
            eve_type=EveType.objects.get(id=33519),
            owner=cls.owner_1102,
            location_flag="AssetSafety",
            material_efficiency=10,
            time_efficiency=30,
            item_id=5,
        )
        cls.owner_1004 = create_owner(character_id=1004, corporation_id=None)
        Blueprint.objects.create(
            location=Location.objects.get(id=60003760),
            eve_type=EveType.objects.get(id=33519),
            owner=cls.owner_1004,
            location_flag="AssetSafety",
            material_efficiency=10,
            time_efficiency=30,
            item_id=6,
        )

    def setUp(self) -> None:
        # given
        self.owner_1001 = create_owner(character_id=1001, corporation_id=None)
        self.user = self.owner_1001.character.user
        add_character_to_user(self.user, EveCharacter.objects.get(character_id=1103))
        Blueprint.objects.create(
            location=Location.objects.get(id=60003760),
            eve_type=EveType.objects.get(id=33519),
            owner=self.owner_1001,
            location_flag="AssetSafety",
            material_efficiency=10,
            time_efficiency=30,
            item_id=1,
        )

    def test_should_return_personal_and_corporation_and_alt_corporation(self):
        # when
        qs = Blueprint.objects.user_has_access(self.user)
        # then
        self.assertSetEqual(set(qs.values_list("item_id", flat=True)), {1, 2, 5})

    def test_should_return_personal_and_corporation_and_alt_corporation_and_alliance(
        self,
    ):
        # given
        self.user = AuthUtils.add_permission_to_user_by_name(
            "blueprints.view_alliance_blueprints", self.user
        )
        # when
        qs = Blueprint.objects.user_has_access(self.user)
        # then
        self.assertSetEqual(set(qs.values_list("item_id", flat=True)), {1, 2, 3, 5, 6})


class TestBlueprintManagerAnnotateLocationName(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_eveuniverse()
        cls.owner = OwnerCharacterFactory()

    def test_should_return_name(self):
        # given
        location = LocationStationFactory(name="Alpha")
        BlueprintFactory(owner=self.owner, location=location)
        # when
        qs = Blueprint.objects.annotate_location_name()
        # then
        obj = qs.first()
        self.assertEqual(obj.location_name, "Alpha")

    def test_should_return_parent_name(self):
        # given
        parent_location = LocationStationFactory(name="Parent")
        child_location = LocationStationFactory(name="", parent=parent_location)
        BlueprintFactory(owner=self.owner, location=child_location)
        # when
        qs = Blueprint.objects.annotate_location_name()
        # then
        obj = qs.first()
        self.assertEqual(obj.location_name, "Parent")

    def test_should_return_generic_name(self):
        # given
        location = LocationStationFactory(name="")
        BlueprintFactory(owner=self.owner, location=location)
        # when
        qs = Blueprint.objects.annotate_location_name()
        # then
        obj = qs.first()
        self.assertEqual(obj.location_name, f"Location #{location.id}")

    def test_should_return_parent_parent_name(self):
        # given
        parent_location = LocationStationFactory(name="Parent")
        child_location = LocationStationFactory(name="", parent=parent_location)
        child_child_location = LocationStationFactory(name="", parent=child_location)
        BlueprintFactory(owner=self.owner, location=child_child_location)
        # when
        qs = Blueprint.objects.annotate_location_name()
        # then
        obj = qs.first()
        self.assertEqual(obj.location_name, "Parent")

    def test_should_return_parent_parent_parent_name(self):
        # given
        parent_location = LocationStationFactory(name="Parent")
        child_location = LocationStationFactory(name="", parent=parent_location)
        child_child_location = LocationStationFactory(name="", parent=child_location)
        child_child_child_location = LocationStationFactory(
            name="", parent=child_child_location
        )
        BlueprintFactory(owner=self.owner, location=child_child_child_location)
        # when
        qs = Blueprint.objects.annotate_location_name()
        # then
        obj = qs.first()
        self.assertEqual(obj.location_name, "Parent")

    def test_should_return_first_parent_with_name_with_4_nodes(self):
        # given
        parent_location = LocationStationFactory(name="Parent")
        child_location = LocationStationFactory(name="Child", parent=parent_location)
        child_child_location = LocationStationFactory(name="", parent=child_location)
        child_child_child_location = LocationStationFactory(
            name="", parent=child_child_location
        )
        BlueprintFactory(owner=self.owner, location=child_child_child_location)
        # when
        qs = Blueprint.objects.annotate_location_name()
        # then
        obj = qs.first()
        self.assertEqual(obj.location_name, "Child")

    def test_should_return_first_parent_with_name_with_3_nodes(self):
        # given
        parent_location = LocationStationFactory(name="Parent")
        child_location = LocationStationFactory(name="Child", parent=parent_location)
        child_child_location = LocationStationFactory(name="", parent=child_location)
        BlueprintFactory(owner=self.owner, location=child_child_location)
        # when
        qs = Blueprint.objects.annotate_location_name()
        # then
        obj = qs.first()
        self.assertEqual(obj.location_name, "Child")


class TestLocationNamePlus(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_eveuniverse()

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


class TestOwner_UpdateLocationsESI(TestCaseWithClearCache):
    # FIXME: This only works when there are 2 items. Why not wiht only one?
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


class TestRequests(TestBlueprintsBase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        # given
        cls.user_1002, _ = create_user_from_evecharacter(1002)
        cls.owner_1001 = create_owner(character_id=1001, corporation_id=2001)
        cls.user_1001 = cls.owner_1001.character.user
        cls.bp_1 = Blueprint.objects.create(
            location=Location.objects.get(id=60003760),
            eve_type=EveType.objects.get(id=33519),
            owner=cls.owner_1001,
            location_flag="AssetSafety",
            material_efficiency=10,
            time_efficiency=30,
            item_id=2,
        )
        cls.owner_1101 = create_owner(character_id=1101, corporation_id=2101)
        cls.bp_2 = Blueprint.objects.create(
            location=Location.objects.get(id=60003760),
            eve_type=EveType.objects.get(id=33519),
            owner=cls.owner_1101,
            location_flag="AssetSafety",
            material_efficiency=10,
            time_efficiency=30,
            item_id=3,
        )

    def test_should_strings(self):
        # given
        req_1 = Request.objects.create(
            blueprint=self.bp_1,
            requesting_user=self.user_1002,
            status=Request.STATUS_OPEN,
        )
        # when/then
        self.assertTrue(str(req_1))
        self.assertTrue(repr(req_1))

    def test_should_return_fulfillable_requests(self):
        # given
        req_1 = Request.objects.create(
            blueprint=self.bp_1,
            requesting_user=self.user_1002,
            status=Request.STATUS_OPEN,
        )
        Request.objects.create(
            blueprint=self.bp_1,
            requesting_user=self.user_1002,
            status=Request.STATUS_FULFILLED,
        )
        Request.objects.create(
            blueprint=self.bp_2,
            requesting_user=self.user_1002,
            status=Request.STATUS_OPEN,
        )
        Request.objects.create(
            blueprint=self.bp_1,
            requesting_user=self.user_1002,
            status=Request.STATUS_OPEN,
            closed_at=now() - dt.timedelta(days=1),
        )
        # when
        result = Request.objects.all().requests_fulfillable_by_user(self.user_1001)
        # then
        result_pks = set(result.values_list("pk", flat=True))
        self.assertSetEqual(result_pks, {req_1.pk})

    def test_should_return_requests_being_fulfilled(self):
        # given
        req_1 = Request.objects.create(
            blueprint=self.bp_1,
            requesting_user=self.user_1002,
            status=Request.STATUS_IN_PROGRESS,
            fulfulling_user=self.user_1001,
        )
        Request.objects.create(
            blueprint=self.bp_1,
            requesting_user=self.user_1002,
            status=Request.STATUS_OPEN,
        )
        Request.objects.create(
            blueprint=self.bp_1,
            requesting_user=self.user_1002,
            status=Request.STATUS_FULFILLED,
        )
        Request.objects.create(
            blueprint=self.bp_2,
            requesting_user=self.user_1002,
            status=Request.STATUS_OPEN,
        )
        Request.objects.create(
            blueprint=self.bp_1,
            requesting_user=self.user_1002,
            status=Request.STATUS_IN_PROGRESS,
            fulfulling_user=self.user_1001,
            closed_at=now() - dt.timedelta(days=1),
        )
        # when
        result = Request.objects.all().requests_being_fulfilled_by_user(self.user_1001)
        # then
        result_pks = set(result.values_list("pk", flat=True))
        self.assertSetEqual(result_pks, {req_1.pk})

    def test_should_return_open_requests_total_count(self):
        # given
        Request.objects.create(
            blueprint=self.bp_1,
            requesting_user=self.user_1002,
            status=Request.STATUS_IN_PROGRESS,
            fulfulling_user=self.user_1001,
        )
        Request.objects.create(
            blueprint=self.bp_1,
            requesting_user=self.user_1002,
            status=Request.STATUS_OPEN,
        )
        Request.objects.create(
            blueprint=self.bp_1,
            requesting_user=self.user_1002,
            status=Request.STATUS_FULFILLED,
        )
        Request.objects.create(
            blueprint=self.bp_2,
            requesting_user=self.user_1002,
            status=Request.STATUS_OPEN,
        )
        Request.objects.create(
            blueprint=self.bp_1,
            requesting_user=self.user_1002,
            status=Request.STATUS_IN_PROGRESS,
            fulfulling_user=self.user_1001,
            closed_at=now() - dt.timedelta(days=1),
        )
        # when
        result = Request.objects.open_requests_total_count(self.user_1001)
        # then
        self.assertEqual(result, 2)
