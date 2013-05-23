from student.models import (User, UserProfile, Registration,
                            CourseEnrollmentAllowed, CourseEnrollment)
from django.contrib.auth.models import Group
from datetime import datetime
from factory import DjangoModelFactory, SubFactory, PostGenerationMethodCall, post_generation, Sequence
from uuid import uuid4


class GroupFactory(DjangoModelFactory):
    FACTORY_FOR = Group

    name = u'staff_MITx/999/Robot_Super_Course'


class UserProfileFactory(DjangoModelFactory):
    FACTORY_FOR = UserProfile

    user = None
    name = u'Robot Test'
    level_of_education = None
    gender = u'm'
    mailing_address = None
    goals = u'World domination'


class RegistrationFactory(DjangoModelFactory):
    FACTORY_FOR = Registration

    user = None
    activation_key = uuid4().hex.decode('ascii')


class UserFactory(DjangoModelFactory):
    FACTORY_FOR = User

    username = Sequence(u'robot{0}'.format)
    email = Sequence(u'robot+test+{0}@edx.org'.format)
    password = PostGenerationMethodCall('set_password',
                                        'test')
    first_name = Sequence(u'Robot{0}'.format)
    last_name = 'Test'
    is_staff = False
    is_active = True
    is_superuser = False
    last_login = datetime(2012, 1, 1)
    date_joined = datetime(2011, 1, 1)

    @post_generation
    def profile(obj, create, extracted, **kwargs):
        if create:
            obj.save()
            return UserProfileFactory.create(user=obj, **kwargs)
        elif kwargs:
            raise Exception("Cannot build a user profile without saving the user")
        else:
            return None


class AdminFactory(UserFactory):
    is_staff = True


class CourseEnrollmentFactory(DjangoModelFactory):
    FACTORY_FOR = CourseEnrollment

    user = SubFactory(UserFactory)
    course_id = u'edX/toy/2012_Fall'


class CourseEnrollmentAllowedFactory(DjangoModelFactory):
    FACTORY_FOR = CourseEnrollmentAllowed

    email = 'test@edx.org'
    course_id = 'edX/test/2012_Fall'
