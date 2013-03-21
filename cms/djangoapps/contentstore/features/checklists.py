from lettuce import world, step
from common import *
from terrain.steps import reload_the_page

############### ACTIONS ####################
@step('I select Checklists from the Tools menu$')
def i_select_checklists(step):
    expand_icon_css = 'li.nav-course-tools i.icon-expand'
    if world.browser.is_element_present_by_css(expand_icon_css):
        css_click(expand_icon_css)
    link_css = 'li.nav-course-tools-checklists a'
    css_click(link_css)


@step('I have opened Checklists$')
def i_have_opened_checklists(step):
    step.given('I have opened a new course in Studio')
    step.given('I select Checklists from the Tools menu')


@step('I see the four default edX checklists$')
def i_see_default_checklists(step):
    checklists = css_find('.checklist-title')
    assert_equal(4, len(checklists))
    assert_true(checklists[0].text.endswith('Getting Started With Studio'))
    assert_true(checklists[1].text.endswith('Draft a Rough Course Outline'))
    assert_true(checklists[2].text.endswith("Explore edX\'s Support Tools"))
    assert_true(checklists[3].text.endswith('Draft Your Course About Page'))


@step('I can check and uncheck tasks in a checklist$')
def i_can_check_and_uncheck_tasks(step):
    # Use the 2nd checklist as a reference
    verifyChecklist2Status(0, 7, 0)
    toggleTask(1, 0)
    verifyChecklist2Status(1, 7, 14)
    toggleTask(1, 3)
    verifyChecklist2Status(2, 7, 29)
    toggleTask(1, 6)
    verifyChecklist2Status(3, 7, 43)
    toggleTask(1, 3)
    verifyChecklist2Status(2, 7, 29)


@step('They are correctly selected after I reload the page$')
def tasks_correctly_selected_after_reload(step):
    reload_the_page(step)
    verifyChecklist2Status(2, 7, 29)
    # verify that task 7 is still selected by toggling its checkbox state and making sure that it deselects
    toggleTask(1, 6)
    verifyChecklist2Status(1, 7, 14)


@step('I select a link to the course outline$')
def i_select_a_link_to_the_course_outline(step):
    clickActionLink(1, 0, 'Edit Course Outline')


@step('I am brought to the course outline page$')
def i_am_brought_to_course_outline(step):
    assert_equal('Course Outline', css_find('.outline .title-1')[0].text)
    assert_equal(1, len(world.browser.windows))


@step('I select a link to help page$')
def i_select_a_link_to_the_help_page(step):
    clickActionLink(2, 0, 'Visit Studio Help')


@step('I am brought to the help page in a new window$')
def i_am_brought_to_help_page_in_new_window(step):
    step.given('I see the four default edX checklists')
    windows = world.browser.windows
    assert_equal(2, len(windows))
    world.browser.switch_to_window(windows[1])
    assert_equal('http://help.edge.edx.org/', world.browser.url)


############### HELPER METHODS ####################
def verifyChecklist2Status(completed, total, percentage):
    def verify_count(driver):
        try:
            statusCount = css_find('#course-checklist1 .status-count').first
            return statusCount.text == str(completed)
        except StaleElementReferenceException:
            return False

    wait_for(verify_count)
    assert_equal(str(total), css_find('#course-checklist1 .status-amount').first.text)
    # Would like to check the CSS width, but not sure how to do that.
    assert_equal(str(percentage), css_find('#course-checklist1 .viz-checklist-status-value .int').first.text)


def toggleTask(checklist, task):
    css_click('#course-checklist' + str(checklist) +'-task' + str(task))


def clickActionLink(checklist, task, actionText):
    # toggle checklist item to make sure that the link button is showing
    toggleTask(checklist, task)
    action_link = css_find('#course-checklist' + str(checklist) + ' a')[task]

    # text will be empty initially, wait for it to populate
    def verify_action_link_text(driver):
        return action_link.text == actionText

    wait_for(verify_action_link_text)
    action_link.click()

