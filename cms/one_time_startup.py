from dogapi import dog_http_api, dog_stats_api
from django.conf import settings
from xmodule.modulestore.django import modulestore

from django.core.cache import get_cache, InvalidCacheBackendError

cache = get_cache('mongo_metadata_inheritance')
for store_name in settings.MODULESTORE:
    store = modulestore(store_name)
    store.metadata_inheritance_cache = cache

if hasattr(settings, 'DATADOG_API'):
    dog_http_api.api_key = settings.DATADOG_API
    dog_stats_api.start(api_key=settings.DATADOG_API, statsd=True)
