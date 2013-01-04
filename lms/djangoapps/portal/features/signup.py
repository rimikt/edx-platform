from lettuce import world, step

@step('I fill in "([^"]*)" on the registration form with "([^"]*)"$')
def when_i_fill_in_field_on_the_registration_form_with_value(step, field, value):
    register_form = world.browser.find_by_css('form#register_form')
    form_field = register_form.find_by_name(field)
    form_field.fill(value)

@step('I press the "([^"]*)" button on the registration form$')
def i_press_the_button_on_the_registration_form(step, button):
    register_form = world.browser.find_by_css('form#register_form')
    register_form.find_by_value(button).click()

@step('I check the checkbox named "([^"]*)"$')
def i_check_checkbox(step, checkbox):
    world.browser.find_by_name(checkbox).check()

@step('I should see "([^"]*)" in the dashboard banner$')
def i_should_see_text_in_the_dashboard_banner_section(step, text):
    css_selector = "section.dashboard-banner h2"
    assert (text in world.browser.find_by_css(css_selector).text)
    