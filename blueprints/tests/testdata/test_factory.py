from app_utils.testing import NoSocketsTestCase

from .factory import (
    OwnerCharacterFactory,
    OwnerCorporationFactory,
    UserMainDefaultFactory,
)


class TestOwnerFactory(NoSocketsTestCase):
    def test_can_create_character_owner(self):
        x = OwnerCharacterFactory()
        self.assertTrue(x.character)
        self.assertFalse(x.corporation)

    def test_can_create_character_owner_from_user(self):
        u = UserMainDefaultFactory()
        x = OwnerCharacterFactory(user=u)
        self.assertEqual(x.character.character, u.profile.main_character)
        self.assertFalse(x.corporation)

    def test_can_create_corporation_owner(self):
        u = UserMainDefaultFactory()
        x = OwnerCorporationFactory(user=u)
        self.assertTrue(x.character)
        self.assertEqual(x.corporation, u.profile.main_character.corporation)
