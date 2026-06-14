"""Decorators for Blueprints."""

from functools import wraps

from allianceauth.services.hooks import get_extension_logger

logger = get_extension_logger(__name__)


# TODO: This is currently not used and can potentially be removed
def fetch_token_for_owner(scopes):
    """returns valid token for owner.
    Needs to be attached on an Owner method !!

    Args:
    -scopes: Provide the required scopes.
    """

    def decorator(func):
        @wraps(func)
        def _wrapped_view(owner, *args, **kwargs):
            token = owner.valid_token(scopes)
            logger.debug(
                "%s: Using token %s for `%s`",
                token.character_name,
                token.pk,
                func.__name__,
            )
            return func(owner, token, *args, **kwargs)

        return _wrapped_view

    return decorator
