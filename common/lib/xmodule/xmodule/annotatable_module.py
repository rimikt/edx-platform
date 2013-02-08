import json
import logging
import re

from lxml import etree
from pkg_resources import resource_string, resource_listdir

from xmodule.x_module import XModule
from xmodule.raw_module import RawDescriptor
from xmodule.modulestore.mongo import MongoModuleStore
from xmodule.modulestore.django import modulestore
from xmodule.contentstore.content import StaticContent

import datetime
import time

log = logging.getLogger(__name__)

class AnnotatableModule(XModule):
    # Note: js and css in common/lib/xmodule/xmodule
    js = {'coffee': [resource_string(__name__, 'js/src/javascript_loader.coffee'),
                     resource_string(__name__, 'js/src/collapsible.coffee'),
                     resource_string(__name__, 'js/src/html/display.coffee'),
                     resource_string(__name__, 'js/src/annotatable/display.coffee')],
          'js': []
         }
    js_module_name = "Annotatable"
    css = {'scss': [resource_string(__name__, 'css/annotatable/display.scss')]}
    icon_class = 'annotatable'

    def _is_span(self, element):
        """ Returns true if the element is a valid annotation span, false otherwise. """
        return element.tag == 'span' and element.get('class') == 'annotatable'

    def _iterspans(self, xmltree, callbacks):
        """ Iterates over span elements and invokes each callback on the span. """

        index = 0
        for element in xmltree.iter('span'):
            if self._is_span(element):
                for callback in callbacks:
                    callback(element, index, xmltree)
                index += 1
 
    def _set_span_data(self, span, index, xmltree):
        """ Sets an ID and discussion anchor for the span. """

        if 'anchor' in span.attrib:
            span.set('data-discussion-anchor', span.get('anchor'))
            del span.attrib['anchor']
    
    def _decorate_span(self, span, index, xmltree):
        """ Decorates the span with an icon and highlight.  """

        cls = ['annotatable', ]
        marker = self._get_marker_color(span)
        if marker is None:
            cls.append('highlight-yellow')
        else:
            cls.append('highlight-'+marker)
        
        span.set('class', ' '.join(cls))
        span_icon = etree.Element('span', { 'class': 'annotatable-icon'} )
        span_icon.text = '';
        span_icon.tail = span.text
        span.text = ''
        span.insert(0, span_icon)
        
    def _decorate_comment(self, span, index, xmltree):
        """ Sets the comment class. """

        comment = None
        for child in span.iterchildren():
            if child.get('class') == 'comment':
                comment = child
                break

        if comment is not None:
            comment.set('class', 'annotatable-comment')

    def _get_marker_color(self, span):
        valid_markers = ['yellow', 'orange', 'purple', 'blue', 'green']
        if 'marker' in span.attrib:
            marker = span.attrib['marker']
            del span.attrib['marker']
            if marker in valid_markers:
                return marker
        return None
    
    def _render(self):
        """ Renders annotatable content by transforming spans and adding discussions. """

        xmltree = etree.fromstring(self.content)
        self._iterspans(xmltree, [ 
            self._set_span_data,
            self._decorate_span,
            self._decorate_comment
        ])

        return etree.tostring(xmltree)

    def get_html(self):
        """ Renders parameters to template. """
        
        context = {
            'display_name': self.display_name,
            'element_id': self.element_id,
            'html_content': self._render()
        }

        # template dir: lms/templates
        return self.system.render_template('annotatable.html', context)

    def __init__(self, system, location, definition, descriptor,
                 instance_state=None, shared_state=None, **kwargs):
        XModule.__init__(self, system, location, definition, descriptor,
                         instance_state, shared_state, **kwargs)
        
        self.element_id = self.location.html_id();
        self.content = self.definition['data']
        self.spans = {} 


class AnnotatableDescriptor(RawDescriptor):
    module_class = AnnotatableModule
    stores_state = True
    template_dir_name = "annotatable"
