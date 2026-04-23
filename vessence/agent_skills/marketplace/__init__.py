"""Facebook Marketplace saved-search harvester and storage.

Public entry points:
    config.list_searches() / get_search(name) / save_search(...)
    harvester.harvest(search_name)  -> runs all queries in the bundle
    harvester.listings_for(search_name) -> latest saved listings

See ``configs/SKILLS_REGISTRY.md`` for the user-facing description.
"""
from . import config, harvester, refresh, summarize  # noqa: F401
