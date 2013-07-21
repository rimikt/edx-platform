import logging
import re

from staticfiles.storage import staticfiles_storage
from staticfiles import finders
from django.conf import settings

from xmodule.modulestore.django import modulestore
from xmodule.modulestore.xml import XMLModuleStore
from xmodule.contentstore.content import StaticContent

log = logging.getLogger(__name__)


def _url_replace_regex(prefix):
    """
    Match static urls in quotes that don't end in '?raw'.

    To anyone contemplating making this more complicated:
    http://xkcd.com/1171/
    """
    return r"""
        (?x)                      # flags=re.VERBOSE
        (?P<quote>\\?['"])        # the opening quotes
        (?P<prefix>{prefix})      # the prefix
        (?P<rest>.*?)             # everything else in the url
        (?P=quote)                # the first matching closing quote
        """.format(prefix=prefix)


def try_staticfiles_lookup(path):
    """
    Try to lookup a path in staticfiles_storage.  If it fails, return
    a dead link instead of raising an exception.
    """
    try:
        url = staticfiles_storage.url(path)
    except Exception as err:
        log.warning("staticfiles_storage couldn't find path {0}: {1}".format(
            path, str(err)))
        # Just return the original path; don't kill everything.
        url = path
    return url


def replace_jump_to_id_urls(text, course_id, jump_to_id_base_url):
    """
    This will replace a link to another piece of courseware to a 'jump_to'
    URL that will redirect to the right place in the courseware

    NOTE: This is similar to replace_course_urls in terms of functionality
    but it is intended to be used when we only have a 'id' that the
    course author provides. This is much more helpful when using
    Studio authored courses since they don't need to know the path. This
    is also durable with respect to item moves.
    """

    def replace_jump_to_id_url(match):
        quote = match.group('quote')
        rest = match.group('rest')
        return "".join([quote, jump_to_id_base_url + rest, quote])

    return re.sub(_url_replace_regex('/jump_to_id/'), replace_jump_to_id_url, text)


def replace_course_urls(text, course_id):
    """
    Replace /course/$stuff urls with /courses/$course_id/$stuff urls

    text: The text to replace
    course_module: A CourseDescriptor

    returns: text with the links replaced
    """

    def replace_course_url(match):
        quote = match.group('quote')
        rest = match.group('rest')
        return "".join([quote, '/courses/' + course_id + '/', rest, quote])

    return re.sub(_url_replace_regex('/course/'), replace_course_url, text)


def replace_static_urls(text, data_directory, course_namespace=None):
    """
    Replace /static/$stuff urls either with their correct url as generated by collectstatic,
    (/static/$md5_hashed_stuff) or by the course-specific content static url
    /static/$course_data_dir/$stuff, or, if course_namespace is not None, by the
    correct url in the contentstore (c4x://)

    text: The source text to do the substitution in
    data_directory: The directory in which course data is stored
    course_namespace: The course identifier used to distinguish static content for this course in studio
    """

    def replace_static_url(match):
        original = match.group(0)
        prefix = match.group('prefix')
        quote = match.group('quote')
        rest = match.group('rest')

        # Don't mess with things that end in '?raw'
        if rest.endswith('?raw'):
            return original

        # In debug mode, if we can find the url as is,
        if settings.DEBUG and finders.find(rest, True):
            return original
        # if we're running with a MongoBacked store course_namespace is not None, then use studio style urls
        elif  course_namespace is not None and not isinstance(modulestore(), XMLModuleStore):
            # first look in the static file pipeline and see if we are trying to reference
            # a piece of static content which is in the mitx repo (e.g. JS associated with an xmodule)
            if staticfiles_storage.exists(rest):
                url = staticfiles_storage.url(rest)
            else:
                # if not, then assume it's courseware specific content and then look in the
                # Mongo-backed database
                url = StaticContent.convert_legacy_static_url(rest, course_namespace)
        # Otherwise, look the file up in staticfiles_storage, and append the data directory if needed
        else:
            course_path = "/".join((data_directory, rest))

            try:
                if staticfiles_storage.exists(rest):
                    url = staticfiles_storage.url(rest)
                else:
                    url = staticfiles_storage.url(course_path)
            # And if that fails, assume that it's course content, and add manually data directory
            except Exception as err:
                log.warning("staticfiles_storage couldn't find path {0}: {1}".format(
                    rest, str(err)))
                url = "".join([prefix, course_path])

        return "".join([quote, url, quote])

    return re.sub(
        _url_replace_regex('/static/(?!{data_dir})'.format(data_dir=data_directory)),
        replace_static_url,
        text
    )
