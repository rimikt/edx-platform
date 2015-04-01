"""
Test the Data Aggregation Layer for Course Enrollments.

"""
import ddt
from mock import patch
from nose.tools import raises
import unittest

from django.conf import settings
from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase
from xmodule.modulestore.tests.factories import CourseFactory
from enrollment.errors import (
    CourseNotFoundError, UserNotFoundError, CourseEnrollmentClosedError,
    CourseEnrollmentFullError, CourseEnrollmentExistsError,
)
from student.tests.factories import UserFactory, CourseModeFactory
from student.models import CourseEnrollment, EnrollmentClosedError, CourseFullError, AlreadyEnrolledError
from enrollment import data


@ddt.ddt
@unittest.skipUnless(settings.ROOT_URLCONF == 'lms.urls', 'Test only valid in lms')
class EnrollmentDataTest(ModuleStoreTestCase):
    """
    Test course enrollment data aggregation.

    """
    USERNAME = "Bob"
    EMAIL = "bob@example.com"
    PASSWORD = "edx"

    def setUp(self):
        """Create a course and user, then log in. """
        super(EnrollmentDataTest, self).setUp()
        self.course = CourseFactory.create()
        self.user = UserFactory.create(username=self.USERNAME, email=self.EMAIL, password=self.PASSWORD)
        self.client.login(username=self.USERNAME, password=self.PASSWORD)

    @ddt.data(
        # Default (no course modes in the database)
        # Expect that users are automatically enrolled as "honor".
        ([], 'honor'),

        # Audit / Verified / Honor
        # We should always go to the "choose your course" page.
        # We should also be enrolled as "honor" by default.
        (['honor', 'verified', 'audit'], 'honor'),
    )
    @ddt.unpack
    def test_enroll(self, course_modes, enrollment_mode):
        # Create the course modes (if any) required for this test case
        self._create_course_modes(course_modes)
        enrollment = data.create_course_enrollment(
            self.user.username,
            unicode(self.course.id),
            enrollment_mode,
            True
        )

        self.assertTrue(CourseEnrollment.is_enrolled(self.user, self.course.id))
        course_mode, is_active = CourseEnrollment.enrollment_mode_for_user(self.user, self.course.id)
        self.assertTrue(is_active)
        self.assertEqual(course_mode, enrollment_mode)

        # Confirm the returned enrollment and the data match up.
        self.assertEqual(course_mode, enrollment['mode'])
        self.assertEqual(is_active, enrollment['is_active'])

    def test_unenroll(self):
        # Enroll the user in the course
        CourseEnrollment.enroll(self.user, self.course.id, mode="honor")

        enrollment = data.update_course_enrollment(
            self.user.username,
            unicode(self.course.id),
            is_active=False
        )

        # Determine that the returned enrollment is inactive.
        self.assertFalse(enrollment['is_active'])

        # Expect that we're no longer enrolled
        self.assertFalse(CourseEnrollment.is_enrolled(self.user, self.course.id))

    @ddt.data(
        # No course modes, no course enrollments.
        ([]),

        # Audit / Verified / Honor course modes, with three course enrollments.
        (['honor', 'verified', 'audit']),
    )
    def test_get_course_info(self, course_modes):
        self._create_course_modes(course_modes, course=self.course)
        result_course = data.get_course_enrollment_info(unicode(self.course.id))
        result_slugs = [mode['slug'] for mode in result_course['course_modes']]
        for course_mode in course_modes:
            self.assertIn(course_mode, result_slugs)

    @ddt.data(
        # No course modes, no course enrollments.
        ([], []),

        # Audit / Verified / Honor course modes, with three course enrollments.
        (['honor', 'verified', 'audit'], ['1', '2', '3']),
    )
    @ddt.unpack
    def test_get_course_enrollments(self, course_modes, course_numbers):
        # Create all the courses
        created_courses = []
        for course_number in course_numbers:
            created_courses.append(CourseFactory.create(number=course_number))

        created_enrollments = []
        for course in created_courses:
            self._create_course_modes(course_modes, course=course)
            # Create the original enrollment.
            created_enrollments.append(data.create_course_enrollment(
                self.user.username,
                unicode(course.id),
                'honor',
                True
            ))

        # Compare the created enrollments with the results
        # from the get enrollments request.
        results = data.get_course_enrollments(self.user.username)
        self.assertEqual(results, created_enrollments)

        # Now create a course enrollment with some invalid course (does
        # not exist in database) for the user and check that the method
        # 'get_course_enrollments' ignores course enrollments for invalid
        # or deleted courses
        CourseEnrollment.objects.create(
            user=self.user,
            course_id='InvalidOrg/InvalidCourse/InvalidRun',
            mode='honor',
            is_active=True
        )
        updated_results = data.get_course_enrollments(self.user.username)
        self.assertEqual(results, updated_results)

    @ddt.data(
        # Default (no course modes in the database)
        # Expect that users are automatically enrolled as "honor".
        ([], 'honor'),

        # Audit / Verified / Honor
        # We should always go to the "choose your course" page.
        # We should also be enrolled as "honor" by default.
        (['honor', 'verified', 'audit'], 'verified'),
    )
    @ddt.unpack
    def test_get_course_enrollment(self, course_modes, enrollment_mode):
        self._create_course_modes(course_modes)

        # Try to get an enrollment before it exists.
        result = data.get_course_enrollment(self.user.username, unicode(self.course.id))
        self.assertIsNone(result)

        # Create the original enrollment.
        enrollment = data.create_course_enrollment(
            self.user.username,
            unicode(self.course.id),
            enrollment_mode,
            True
        )
        # Get the enrollment and compare it to the original.
        result = data.get_course_enrollment(self.user.username, unicode(self.course.id))
        self.assertEqual(self.user.username, result['user'])
        self.assertEqual(enrollment, result)

    @raises(CourseNotFoundError)
    def test_non_existent_course(self):
        data.get_course_enrollment_info("this/is/bananas")

    def _create_course_modes(self, course_modes, course=None):
        """Create the course modes required for a test. """
        course_id = course.id if course else self.course.id
        for mode_slug in course_modes:
            CourseModeFactory.create(
                course_id=course_id,
                mode_slug=mode_slug,
                mode_display_name=mode_slug,
            )

    @raises(UserNotFoundError)
    def test_enrollment_for_non_existent_user(self):
        data.create_course_enrollment("some_fake_user", unicode(self.course.id), 'honor', True)

    @raises(CourseNotFoundError)
    def test_enrollment_for_non_existent_course(self):
        data.create_course_enrollment(self.user.username, "some/fake/course", 'honor', True)

    @raises(CourseEnrollmentClosedError)
    @patch.object(CourseEnrollment, "enroll")
    def test_enrollment_for_closed_course(self, mock_enroll):
        mock_enroll.side_effect = EnrollmentClosedError("Bad things happened")
        data.create_course_enrollment(self.user.username, unicode(self.course.id), 'honor', True)

    @raises(CourseEnrollmentFullError)
    @patch.object(CourseEnrollment, "enroll")
    def test_enrollment_for_closed_course(self, mock_enroll):
        mock_enroll.side_effect = CourseFullError("Bad things happened")
        data.create_course_enrollment(self.user.username, unicode(self.course.id), 'honor', True)

    @raises(CourseEnrollmentExistsError)
    @patch.object(CourseEnrollment, "enroll")
    def test_enrollment_for_closed_course(self, mock_enroll):
        mock_enroll.side_effect = AlreadyEnrolledError("Bad things happened")
        data.create_course_enrollment(self.user.username, unicode(self.course.id), 'honor', True)

    @raises(UserNotFoundError)
    def test_update_for_non_existent_user(self):
        data.update_course_enrollment("some_fake_user", unicode(self.course.id), is_active=False)

    def test_update_for_non_existent_course(self):
        enrollment = data.update_course_enrollment(self.user.username, "some/fake/course", is_active=False)
        self.assertIsNone(enrollment)
