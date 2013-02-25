import logging

from lxml import etree
from pkg_resources import resource_string, resource_listdir

from xmodule.x_module import XModule
from xmodule.raw_module import RawDescriptor
from xmodule.modulestore.mongo import MongoModuleStore
from xmodule.modulestore.django import modulestore
from xmodule.contentstore.content import StaticContent

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

    def _get_annotation_class_attr(self, index, el):
        """ Returns a dict with the CSS class attribute to set on the annotation
            and an XML key to delete from the element.
         """

        attr = {}
        cls = ['annotatable-span', 'highlight']
        valid_colors = ['yellow', 'orange', 'purple', 'blue', 'green']
        highlight_key = 'highlight'

        color = el.get(highlight_key)
        if color is not None and color in valid_colors:
            cls.append('highlight-'+color)
            attr['_delete'] = highlight_key

        attr['value'] = ' '.join(cls)

        return { 'class' : attr }

    def _get_annotation_data_attr(self, index, el):
        """ Returns a dict in which the keys are the HTML data attributes
            to set on the annotation element. Each data attribute has a
            corresponding 'value' and (optional) '_delete' key to specify
            an XML attribute to delete.
        """

        data_attrs = {}
        attrs_map = {
            'body': 'data-comment-body',
            'title': 'data-comment-title',
            'problem': 'data-problem-id'
        }

        for xml_key in attrs_map.keys():
            if xml_key in el.attrib:
                value = el.get(xml_key, '')
                html_key = attrs_map[xml_key]
                data_attrs[html_key] = { 'value': value, '_delete': xml_key }

        return data_attrs

    def _render_content(self):
        """ Renders annotatable content with annotation spans and returns HTML. """

        xmltree = etree.fromstring(self.content)
        xmltree.tag = 'div'

        index = 0
        for el in xmltree.findall('.//annotation'):
            el.tag = 'span'

            attr = {}
            attr.update(self._get_annotation_class_attr(index, el))
            attr.update(self._get_annotation_data_attr(index, el))
            for key in attr.keys():
                el.set(key, attr[key]['value'])
                if '_delete' in attr[key]:
                    delete_key = attr[key]['_delete']
                    del el.attrib[delete_key]
            index += 1

        return etree.tostring(xmltree, encoding='unicode')

    def get_html(self):
        """ Renders parameters to template. """
        context = {
            'display_name': self.display_name,
            'element_id': self.element_id,
            'discussion_id': self.discussion_id,
            'instructions_html': self.instructions_html,
            'content_html': self._render_content()
        }

        return self.system.render_template('annotatable.html', context)

    def __init__(self, system, location, definition, descriptor,
                 instance_state=None, shared_state=None, **kwargs):
        XModule.__init__(self, system, location, definition, descriptor,
                         instance_state, shared_state, **kwargs)

        self.element_id = self.location.html_id()

        xmltree = etree.fromstring(self.definition['data'])

        # extract discussion id
        self.discussion_id = xmltree.get('discussion', '')
        del xmltree.attrib['discussion']

        # extract instructions text (if any)
        instructions = xmltree.find('instructions')
        instructions_html = None
        if instructions is not None:
            instructions.tag = 'div'
            instructions_html = etree.tostring(instructions, encoding='unicode')
            xmltree.remove(instructions)
        self.instructions_html = instructions_html

        # everything else is annotatable content
        self.content = etree.tostring(xmltree, encoding='unicode')

class AnnotatableDescriptor(RawDescriptor):
    module_class = AnnotatableModule
    stores_state = True
    template_dir_name = "annotatable"

