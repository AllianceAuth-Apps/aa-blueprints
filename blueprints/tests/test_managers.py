import datetime as dt

from django.utils.timezone import now

from app_utils.testdata_factories import (
    EveAllianceInfoFactory,
    EveCharacterFactory,
    EveCorporationInfoFactory,
    UserMainFactory,
)
from app_utils.testing import NoSocketsTestCase, add_character_to_user

from blueprints.models import Blueprint, Request
from blueprints.tests.helpers import extract
from blueprints.tests.testdata.factory import (
    BlueprintFactory,
    LocationStationFactory,
    OwnerCharacterFactory,
    OwnerCorporationFactory,
    RequestFactory,
    UserMainCorporationFactory,
    UserMainDefaultFactory,
)


class TestBlueprintQuerySet(NoSocketsTestCase):
    def test_should_annotate_is_bpo(self):
        # given
        bp_1 = BlueprintFactory(runs=10)
        bp_2 = BlueprintFactory()

        # when
        qs = Blueprint.objects.all().annotate_is_bpo()

        # then
        obj_1 = qs.get(item_id=bp_1.item_id)
        self.assertEqual(obj_1.is_bpo, "no")
        obj_2 = qs.get(item_id=bp_2.item_id)
        self.assertEqual(obj_2.is_bpo, "yes")

    def test_should_annotate_owner_name(self):
        # given
        owner_1 = OwnerCharacterFactory()
        bp_1 = BlueprintFactory(owner=owner_1)
        owner_2 = OwnerCorporationFactory()
        bp_2 = BlueprintFactory(owner=owner_2)

        # when
        qs = Blueprint.objects.all().annotate_owner_name()

        # then
        obj_1 = qs.get(item_id=bp_1.item_id)
        self.assertEqual(obj_1.owner_name, owner_1.eve_character_strict.character_name)
        obj_2 = qs.get(item_id=bp_2.item_id)
        self.assertEqual(obj_2.owner_name, owner_2.corporation_strict.corporation_name)


class TestBlueprintManager_UserHasAccess(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        # given
        alliance = EveAllianceInfoFactory()
        cls.corporation_2001 = EveCorporationInfoFactory(
            corporation_id=2001, alliance=alliance
        )
        character_1002 = EveCharacterFactory(
            character_id=1002, corporation=cls.corporation_2001
        )
        corporation_2002 = EveCorporationInfoFactory(
            corporation_id=2002, alliance=alliance
        )
        character_1003 = EveCharacterFactory(
            character_id=1003, corporation=corporation_2002
        )

        owner_1002 = OwnerCorporationFactory(
            user=UserMainCorporationFactory(main_character__character=character_1002)
        )
        BlueprintFactory(owner=owner_1002, item_id=2)
        owner_1003 = OwnerCorporationFactory(
            user=UserMainCorporationFactory(main_character__character=character_1003)
        )
        BlueprintFactory(owner=owner_1003, item_id=3)
        owner_1101 = OwnerCorporationFactory()
        BlueprintFactory(owner=owner_1101, item_id=4)
        owner_1004 = OwnerCharacterFactory()
        BlueprintFactory(owner=owner_1004, item_id=6)  # should not be visible at all

    def test_should_return_personal_and_corporation_and_alt_corporation(self):
        # given
        character_1001 = EveCharacterFactory(
            character_id=1001, corporation=self.corporation_2001
        )
        user = UserMainFactory(
            main_character__character=character_1001,
            permissions__=[
                "blueprints.basic_access",
                "blueprints.add_personal_blueprint_owner",
            ],
        )

        owner_1001 = OwnerCharacterFactory(user=user)
        BlueprintFactory(owner=owner_1001, item_id=1)

        character_1103 = EveCharacterFactory(character_id=1103)
        add_character_to_user(user, character_1103)
        owner_1102 = OwnerCorporationFactory(
            user=user, corporation=character_1103.corporation
        )
        BlueprintFactory(owner=owner_1102, item_id=5)

        # when
        qs = Blueprint.objects.user_has_access(user)

        # then
        got = extract(qs, "item_id")
        want = {1, 2, 5}
        self.assertSetEqual(got, want)

    def test_should_return_personal_and_corporation_and_alt_corporation_and_alliance(
        self,
    ):
        # given
        character_1001 = EveCharacterFactory(
            character_id=1001, corporation=self.corporation_2001
        )
        user = UserMainFactory(
            main_character__character=character_1001,
            permissions__=[
                "blueprints.basic_access",
                "blueprints.add_personal_blueprint_owner",
                "blueprints.view_alliance_blueprints",
            ],
        )

        owner_1001 = OwnerCharacterFactory(user=user)
        BlueprintFactory(owner=owner_1001, item_id=1)

        character_1103 = EveCharacterFactory(character_id=1103)
        add_character_to_user(user, character_1103)
        owner_1102 = OwnerCorporationFactory(
            user=user, corporation=character_1103.corporation
        )
        BlueprintFactory(owner=owner_1102, item_id=5)

        # when
        qs = Blueprint.objects.user_has_access(user)

        # then
        got = extract(qs, "item_id")
        want = {1, 2, 3, 5}
        self.assertSetEqual(got, want)

    # def test_should_return_personal_and_corporation_and_alt_corporation_and_alliance_(
    #     self,
    # ):
    #     # given
    #     self.user = AuthUtils.add_permission_to_user_by_name(
    #         "blueprints.view_alliance_blueprints", self.user
    #     )
    #     # when
    #     qs = Blueprint.objects.user_has_access(self.user)
    #     # then
    #     self.assertSetEqual(set(qs.values_list("item_id", flat=True)), {1, 2, 3, 5, 6})


class TestBlueprintManager_AnnotateLocationName(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
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


class TestRequestManager(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        corporation = EveCorporationInfoFactory()
        cls.user_1 = UserMainDefaultFactory(
            main_character__character=EveCharacterFactory(corporation=corporation)
        )
        cls.user_2 = UserMainDefaultFactory(
            main_character__character=EveCharacterFactory(corporation=corporation)
        )

        cls.bp_1 = BlueprintFactory(owner=OwnerCorporationFactory(user=cls.user_1))
        cls.bp_2 = BlueprintFactory()  # bp owned by someone outside corporation

    def test_should_return_fulfillable_requests(self):
        # given
        req = RequestFactory(
            blueprint=self.bp_1,
            requesting_user=self.user_1,
            status=Request.STATUS_OPEN,
        )
        RequestFactory(
            blueprint=self.bp_1,
            requesting_user=self.user_1,
            status=Request.STATUS_FULFILLED,
        )
        RequestFactory(
            blueprint=self.bp_2,
            requesting_user=self.user_1,
            status=Request.STATUS_OPEN,
        )
        RequestFactory(
            blueprint=self.bp_1,
            requesting_user=self.user_1,
            status=Request.STATUS_OPEN,
            closed_at=now() - dt.timedelta(days=1),
        )

        # when
        qs = Request.objects.all().requests_fulfillable_by_user(self.user_2)

        # then
        self.assertCountEqual(qs, [req])

    def test_should_return_requests_being_fulfilled(self):
        # given
        req = RequestFactory(
            blueprint=self.bp_1,
            requesting_user=self.user_1,
            status=Request.STATUS_IN_PROGRESS,
            fulfulling_user=self.user_2,
        )
        RequestFactory(
            blueprint=self.bp_1,
            requesting_user=self.user_1,
            status=Request.STATUS_FULFILLED,
        )
        RequestFactory(
            blueprint=self.bp_2,
            requesting_user=self.user_1,
            status=Request.STATUS_OPEN,
        )
        RequestFactory(
            blueprint=self.bp_1,
            requesting_user=self.user_1,
            status=Request.STATUS_OPEN,
            closed_at=now() - dt.timedelta(days=1),
        )

        # when
        qs = Request.objects.all().requests_being_fulfilled_by_user(self.user_2)

        # then
        self.assertCountEqual(qs, [req])

    def test_should_return_open_requests_total_count(self):
        # given
        RequestFactory(
            blueprint=self.bp_1,
            requesting_user=self.user_1,
            status=Request.STATUS_IN_PROGRESS,
            fulfulling_user=self.user_2,
        )
        RequestFactory(
            blueprint=self.bp_1,
            requesting_user=self.user_1,
            status=Request.STATUS_OPEN,
        )
        RequestFactory(
            blueprint=self.bp_1,
            requesting_user=self.user_1,
            status=Request.STATUS_FULFILLED,
        )
        RequestFactory(
            blueprint=self.bp_2,
            requesting_user=self.user_1,
            status=Request.STATUS_OPEN,
        )
        RequestFactory(
            blueprint=self.bp_1,
            requesting_user=self.user_1,
            status=Request.STATUS_IN_PROGRESS,
            fulfulling_user=self.user_2,
            closed_at=now() - dt.timedelta(days=1),
        )
        # when
        result = Request.objects.open_requests_total_count(self.user_2)
        # then
        self.assertEqual(result, 2)
