"""Tests for Django management commands"""

import json
from StringIO import StringIO

from django.core.management import call_command
from django.test.utils import override_settings

from courseware.tests.tests import TEST_DATA_MONGO_MODULESTORE

from xmodule.modulestore.django import modulestore
from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase
from xmodule.modulestore.xml_importer import import_from_xml

DATA_DIR = 'common/test/data/'


@override_settings(MODULESTORE=TEST_DATA_MONGO_MODULESTORE)
class CommandTestCase(ModuleStoreTestCase):
    """Parent class with helpers for testing management commands"""

    def load_courses(self):
        """Load test courses and return list of ids"""
        store = modulestore()
        import_from_xml(store, DATA_DIR, ['toy', 'simple'])
        return [course.id for course in store.get_courses()]

    def call_command(self, name, *args, **kwargs):
        """Call management command and return output"""
        out = StringIO()  # To Capture the output of the command
        call_command(name, *args, stdout=out, **kwargs)
        out.seek(0)
        return out.read()


class CommandsTestCase(CommandTestCase):
    """Test case for management commands"""

    def setUp(self):
        self.loaded_courses = self.load_courses()

    def test_dump_course_ids(self):
        kwargs = {'modulestore': 'default'}
        output = self.call_command('dump_course_ids', **kwargs)
        dumped_courses = output.strip().split('\n')
        self.assertEqual(self.loaded_courses, dumped_courses)

    def test_dump_course_structure(self):

        args = ['edX/simple/2012_Fall']
        kwargs = {'modulestore': 'default'}
        output = self.call_command('dump_course_structure', *args, **kwargs)

        dump = json.loads(output)

        # Check a few elements in the course dump

        parent_id = 'i4x://edX/simple/chapter/Overview'
        self.assertEqual(dump[parent_id]['category'], 'chapter')
        self.assertEqual(len(dump[parent_id]['children']), 3)

        child_id = dump[parent_id]['children'][1]
        self.assertEqual(dump[child_id]['category'], 'videosequence')
        self.assertEqual(len(dump[child_id]['children']), 2)

        video_id = 'i4x://edX/simple/video/Welcome'
        self.assertEqual(dump[video_id]['category'], 'video')
        self.assertEqual(len(dump[video_id]['metadata']), 4)
        self.assertIn('youtube_id_1_0', dump[video_id]['metadata'])

        # Check if there is the right number of elements

        self.assertEqual(len(dump), 16)
