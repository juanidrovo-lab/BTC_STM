"""Factory that returns the appropriate session store based on runtime settings."""

from __future__ import annotations

from pathlib import Path

from btc_stm.persistence.local_store import LocalSessionStore
from btc_stm.persistence.neon_store import NeonSessionStore
from btc_stm.settings import Settings


def get_store(
    settings: Settings,
    base_dir: Path | None = None,
) -> LocalSessionStore | NeonSessionStore:
    """Return the session store configured by ``settings``.

    Parameters
    ----------
    settings:
        Application settings.  Reads ``persistence_backend`` and
        ``database_url``.
    base_dir:
        Required when ``persistence_backend`` is ``"local"``.  The root
        directory where session artefacts will be written.

    Returns
    -------
    LocalSessionStore | NeonSessionStore
        Concrete store instance ready for use.

    Raises
    ------
    ValueError
        If required configuration is missing for the selected backend.
    """
    if settings.persistence_backend == "neon":
        if not settings.database_url:
            raise ValueError(
                "DATABASE_URL is required when PERSISTENCE_BACKEND=neon"
            )
        return NeonSessionStore(database_url=settings.database_url)

    # default: local filesystem store
    if base_dir is None:
        raise ValueError("base_dir is required for local persistence backend")

    from btc_stm.persistence.models import PersistenceConfig  # noqa: PLC0415

    return LocalSessionStore(PersistenceConfig(base_dir=base_dir))
