"""
Functions that can are used to modify XBlock fragments for use in the LMS and Studio
"""

import datetime
import json
import logging
import static_replace

from django.conf import settings
from django.utils.timezone import UTC
from mitxmako.shortcuts import render_to_string
from xblock.fragment import Fragment

from xmodule.seq_module import SequenceModule
from xmodule.vertical_module import VerticalModule

log = logging.getLogger(__name__)


def wrap_fragment(fragment, new_content):
    """
    Returns a new Fragment that has `new_content` and all
    as its content, and all of the resources from fragment
    """
    wrapper_frag = Fragment(content=new_content)
    wrapper_frag.add_frag_resources(fragment)
    return wrapper_frag


def wrap_xmodule(template, block, view, frag, context):  # pylint: disable=unused-argument
    """
    Wraps the results of get_html in a standard <section> with identifying
    data so that the appropriate javascript module can be loaded onto it.

    get_html: An XModule.get_html method or an XModuleDescriptor.get_html method
    module: An XModule
    template: A template that takes the variables:
        content: the results of get_html,
        display_name: the display name of the xmodule, if available (None otherwise)
        class_: the module class name
        module_name: the js_module_name of the module
    """

    # If XBlock generated this class, then use the first baseclass
    # as the name (since that's the original, unmixed class)
    class_name = getattr(block, 'unmixed_class', block.__class__).__name__

    template_context = {
        'content': frag.content,
        'display_name': block.display_name,
        'class_': class_name,
        'module_name': block.js_module_name,
    }

    return wrap_fragment(frag, render_to_string(template, template_context))


def replace_jump_to_id_urls(course_id, jump_to_id_base_url, block, view, frag, context):  # pylint: disable=unused-argument
    """
    This will replace a link between courseware in the format
    /jump_to/<id> with a URL for a page that will correctly redirect
    This is similar to replace_course_urls, but much more flexible and
    durable for Studio authored courses. See more comments in static_replace.replace_jump_to_urls

    course_id: The course_id in which this rewrite happens
    jump_to_id_base_url:
        A app-tier (e.g. LMS) absolute path to the base of the handler that will perform the
        redirect. e.g. /courses/<org>/<course>/<run>/jump_to_id. NOTE the <id> will be appended to
        the end of this URL at re-write time

    output: a new :class:`~xblock.fragment.Fragment` that modifies `frag` with
        content that has been update with /jump_to links replaced
    """
    return wrap_fragment(frag, static_replace.replace_jump_to_id_urls(frag.content, course_id, jump_to_id_base_url))


def replace_course_urls(course_id, block, view, frag, context):  # pylint: disable=unused-argument
    """
    Updates the supplied module with a new get_html function that wraps
    the old get_html function and substitutes urls of the form /course/...
    with urls that are /courses/<course_id>/...
    """
    return wrap_fragment(frag, static_replace.replace_course_urls(frag.content, course_id))


def replace_static_urls(data_dir, block, view, frag, context, course_id=None, static_asset_path=''):  # pylint: disable=unused-argument
    """
    Updates the supplied module with a new get_html function that wraps
    the old get_html function and substitutes urls of the form /static/...
    with urls that are /static/<prefix>/...
    """
    return wrap_fragment(frag, static_replace.replace_static_urls(
        frag.content,
        data_dir,
        course_id,
        static_asset_path=static_asset_path
    ))


def grade_histogram(module_id):
    ''' Print out a histogram of grades on a given problem.
        Part of staff member debug info.
    '''
    from django.db import connection
    cursor = connection.cursor()

    q = """SELECT courseware_studentmodule.grade,
                  COUNT(courseware_studentmodule.student_id)
    FROM courseware_studentmodule
    WHERE courseware_studentmodule.module_id=%s
    GROUP BY courseware_studentmodule.grade"""
    # Passing module_id this way prevents sql-injection.
    cursor.execute(q, [module_id])

    grades = list(cursor.fetchall())
    grades.sort(key=lambda x: x[0])  # Add ORDER BY to sql query?
    if len(grades) >= 1 and grades[0][0] is None:
        return []
    return grades


def add_histogram(user, block, view, frag, context):  # pylint: disable=unused-argument
    """
    Updates the supplied module with a new get_html function that wraps
    the output of the old get_html function with additional information
    for admin users only, including a histogram of student answers and the
    definition of the xmodule

    Does nothing if module is a SequenceModule or a VerticalModule.
    """
    # TODO: make this more general, eg use an XModule attribute instead
    if isinstance(block, (SequenceModule, VerticalModule)):
        return frag

    block_id = block.id
    if block.has_score:
        histogram = grade_histogram(block_id)
        render_histogram = len(histogram) > 0
    else:
        histogram = None
        render_histogram = False

    if settings.MITX_FEATURES.get('ENABLE_LMS_MIGRATION'):
        [filepath, filename] = getattr(block, 'xml_attributes', {}).get('filename', ['', None])
        osfs = block.system.filestore
        if filename is not None and osfs.exists(filename):
            # if original, unmangled filename exists then use it (github
            # doesn't like symlinks)
            filepath = filename
        data_dir = block.static_asset_path or osfs.root_path.rsplit('/')[-1]
        giturl = block.giturl or 'https://github.com/MITx'
        edit_link = "%s/%s/tree/master/%s" % (giturl, data_dir, filepath)
    else:
        edit_link = False
        # Need to define all the variables that are about to be used
        giturl = ""
        data_dir = ""

    source_file = block.source_file  # source used to generate the problem XML, eg latex or word

    # useful to indicate to staff if problem has been released or not
    # TODO (ichuang): use _has_access_descriptor.can_load in lms.courseware.access, instead of now>mstart comparison here
    now = datetime.datetime.now(UTC())
    is_released = "unknown"
    mstart = block.start

    if mstart is not None:
        is_released = "<font color='red'>Yes!</font>" if (now > mstart) else "<font color='green'>Not yet</font>"

    staff_context = {'fields': [(name, field.read_from(block)) for name, field in block.fields.items()],
                     'xml_attributes': getattr(block, 'xml_attributes', {}),
                     'location': block.location,
                     'xqa_key': block.xqa_key,
                     'source_file': source_file,
                     'source_url': '%s/%s/tree/master/%s' % (giturl, data_dir, source_file),
                     'category': str(block.__class__.__name__),
                     # Template uses element_id in js function names, so can't allow dashes
                     'element_id': block.location.html_id().replace('-', '_'),
                     'edit_link': edit_link,
                     'user': user,
                     'xqa_server': settings.MITX_FEATURES.get('USE_XQA_SERVER', 'http://xqa:server@content-qa.mitx.mit.edu/xqa'),
                     'histogram': json.dumps(histogram),
                     'render_histogram': render_histogram,
                     'block_content': frag.content,
                     'is_released': is_released,
                     }
    return wrap_fragment(frag, render_to_string("staff_problem_info.html", staff_context))
