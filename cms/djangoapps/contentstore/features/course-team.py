#pylint: disable=C0111
#pylint: disable=W0621

from lettuce import world, step
from common import create_studio_user, log_into_studio, COURSE_NAME

PASSWORD = 'test'
EMAIL_EXTENSION = '@edx.org'


@step(u'I am viewing the course team settings')
def view_grading_settings(step):
    world.click_course_settings()
    link_css = 'li.nav-course-settings-team a'
    world.css_click(link_css)


@step(u'The user "([^"]*)" exists$')
def create_other_user(step, name):
    create_studio_user(uname=name, password=PASSWORD, email=(name + EMAIL_EXTENSION))


@step(u'I add "([^"]*)" to the course team')
def add_other_user(step, name):
    new_user_css = 'a.new-user-button'
    world.css_click(new_user_css)

    email_css = 'input.email-input'
    f = world.css_find(email_css)
    f._element.send_keys(name, EMAIL_EXTENSION)

    confirm_css = '#add_user'
    world.css_click(confirm_css)


@step(u'I delete "([^"]*)" from the course team')
def delete_other_user(step, name):
    to_delete_css = '.remove-user[data-id="{name}{extension}"]'.format(name=name, extension=EMAIL_EXTENSION,)
    world.css_click(to_delete_css)


@step(u'"([^"]*)" logs in$')
def other_user_login(step, name):
    log_into_studio(uname=name, password=PASSWORD, email=name + EMAIL_EXTENSION)


@step(u'He does( not)? see the course on his page')
def see_course(step, doesnt_see_course):
    class_css = '.class-name'
    all_courses = world.css_find(class_css)
    all_names = [item.html for item in all_courses]
    if doesnt_see_course:
        assert not COURSE_NAME in all_names
    else:
        assert COURSE_NAME in all_names


@step(u'He cannot delete users')
def cannot_delete(step):
    to_delete_css = '.remove-user'
    assert world.is_css_not_present(to_delete_css)


@step(u'He cannot add users')
def cannot_add(step):
    add_css = '.new-user'
    assert world.is_css_not_present(add_css)
