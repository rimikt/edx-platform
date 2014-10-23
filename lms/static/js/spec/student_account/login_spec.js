define([
    'jquery',
    'underscore',
    'js/common_helpers/template_helpers',
    'js/common_helpers/ajax_helpers',
    'js/student_account/models/LoginModel',
    'js/student_account/views/LoginView'
], function($, _, TemplateHelpers, AjaxHelpers, LoginModel, LoginView) {
        describe('edx.student.account.LoginView', function() {
            'use strict';

            var model = null,
                view = null,
                requests = null,
                PLATFORM_NAME = 'edX',
                USER_DATA = {
                    email: 'xsy@edx.org',
                    password: 'xsyisawesome',
                    remember: true
                },
                THIRD_PARTY_AUTH = {
                    currentProvider: null,
                    providers: [
                        {
                            name: 'Google',
                            iconClass: 'icon-google-plus',
                            loginUrl: '/auth/login/google-oauth2/?auth_entry=account_login',
                            registerUrl: '/auth/login/google-oauth2/?auth_entry=account_register'
                        },
                        {
                            name: 'Facebook',
                            iconClass: 'icon-facebook',
                            loginUrl: '/auth/login/facebook/?auth_entry=account_login',
                            registerUrl: '/auth/login/facebook/?auth_entry=account_register'
                        }
                    ]
                },
                FORM_DESCRIPTION = {
                    method: 'post',
                    submit_url: '/user_api/v1/account/login_session/',
                    fields: [
                        {
                            name: 'email',
                            label: 'Email',
                            defaultValue: '',
                            type: 'email',
                            required: true,
                            placeholder: 'place@holder.org',
                            instructions: 'Enter your email.',
                            restrictions: {}
                        },
                        {
                            name: 'password',
                            label: 'Password',
                            defaultValue: '',
                            type: 'password',
                            required: true,
                            instructions: 'Enter your password.',
                            restrictions: {}
                        },
                        {
                            name: 'remember',
                            label: 'Remember me',
                            defaultValue: '',
                            type: 'checkbox',
                            required: true,
                            instructions: "Agree to the terms of service.",
                            restrictions: {}
                        }
                    ]
                };

            var createLoginView = function(test) {
                // Initialize the login model
                model = new LoginModel({ url: FORM_DESCRIPTION.submit_url });

                // Initialize the login view
                view = new LoginView({
                    fields: FORM_DESCRIPTION.fields,
                    model: model,
                    thirdPartyAuth: THIRD_PARTY_AUTH,
                    platformName: PLATFORM_NAME
                });

                // Spy on AJAX requests
                requests = AjaxHelpers.requests(test);

                // Mock out redirection logic
                spyOn(view, 'redirect').andCallFake(function() {
                    return true;
                });
            };

            var submitForm = function(validationSuccess) {
                // Simulate manual entry of login form data
                $('#login-email').val(USER_DATA.email);
                $('#login-password').val(USER_DATA.password);

                // Check the "Remember me" checkbox
                $('#login-remember').prop('checked', USER_DATA.remember);

                // Create a fake click event
                var clickEvent = $.Event('click');

                // If validationSuccess isn't passed, we avoid
                // spying on `view.validate` twice
                if ( !_.isUndefined(validationSuccess) ) {
                    // Force validation to return as expected
                    spyOn(view, 'validate').andReturn({
                        isValid: validationSuccess,
                        message: 'Submission was validated.'
                    });
                }

                // Submit the email address
                view.submitForm(clickEvent);
            };

            beforeEach(function() {
                setFixtures('<div id="login-form"></div>');
                TemplateHelpers.installTemplate('templates/student_account/login');
                TemplateHelpers.installTemplate('templates/student_account/form_field');
            });

            it('logs the user in', function() {
                createLoginView(this);

                // Submit the form, with successful validation
                submitForm(true);

                // Verify that the client contacts the server with the expected data
                AjaxHelpers.expectRequest(
                    requests, 'POST', FORM_DESCRIPTION.submit_url, $.param(
                        $.extend({url: FORM_DESCRIPTION.submit_url}, USER_DATA)
                    )
                );

                // Respond with status code 200
                AjaxHelpers.respondWithJson(requests, {});

                // Verify that the user is redirected to the dashboard
                expect(view.redirect).toHaveBeenCalledWith('/dashboard');
            });

            it('displays third-party auth login buttons', function() {
                createLoginView(this);

                // Verify that Google and Facebook registration buttons are displayed
                expect($('.button-Google')).toBeVisible();
                expect($('.button-Facebook')).toBeVisible();
            });

            it('displays a link to the password reset form', function() {
                createLoginView(this);

                // Verify that the password reset link is displayed
                expect($('.forgot-password')).toBeVisible();
            });

            it('validates login form fields', function() {
                createLoginView(this);

                submitForm(true);

                // Verify that validation of form fields occurred
                expect(view.validate).toHaveBeenCalledWith($('#login-email')[0]);
                expect(view.validate).toHaveBeenCalledWith($('#login-password')[0]);
            });

            it('displays login form validation errors', function() {
                createLoginView(this);

                // Submit the form, with failed validation
                submitForm(false);

                // Verify that submission errors are visible
                expect(view.$errors).not.toHaveClass('hidden');
            });

            it('displays an error if the server returns an error while logging in', function() {
                createLoginView(this);

                // Submit the form, with successful validation
                submitForm(true);

                // Simulate an error from the LMS servers
                AjaxHelpers.respondWithError(requests);

                // Expect that an error is displayed, and that we haven't been redirected
                expect(view.$errors).not.toHaveClass('hidden');
                expect(view.redirect).not.toHaveBeenCalled();

                // If we try again and succeed, the error should go away
                submitForm();

                // This time, respond with status code 200
                AjaxHelpers.respondWithJson(requests, {});

                // Expect that the error is hidden
                expect(view.$errors).toHaveClass('hidden');
            });
        });
    }
);
