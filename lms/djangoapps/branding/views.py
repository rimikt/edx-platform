from django.conf import settings
from django.core.urlresolvers import reverse
from django.shortcuts import redirect
from django_future.csrf import ensure_csrf_cookie

import student.views
import branding
import courseware.views
from mitxmako.shortcuts import marketing_link
from util.cache import cache_if_anonymous


@ensure_csrf_cookie
@cache_if_anonymous
def index(request):
    '''
    Redirects to main page -- info page if user authenticated, or marketing if not
    '''

    if settings.COURSEWARE_ENABLED and request.user.is_authenticated():
        return redirect(reverse('dashboard'))

    if settings.MITX_FEATURES.get('AUTH_USE_MIT_CERTIFICATES'):
        from external_auth.views import ssl_login
        return ssl_login(request)
    if settings.MITX_FEATURES.get('ENABLE_MKTG_SITE'):
         return redirect(settings.MKTG_URLS.get('ROOT'))

    university = branding.get_university(request.META.get('HTTP_HOST'))
    if university is None:
        return student.views.index(request, user=request.user)

    return courseware.views.university_profile(request, university)


@ensure_csrf_cookie
@cache_if_anonymous
def courses(request):
    """
    Render the "find courses" page. If the marketing site is enabled, redirect
    to that. Otherwise, if subdomain branding is on, this is the university
    profile page. Otherwise, it's the edX courseware.views.courses page
    """
    if settings.MITX_FEATURES.get('ENABLE_MKTG_SITE', False):
        return redirect(marketing_link('COURSES'), permanent=True)

    university = branding.get_university(request.META.get('HTTP_HOST'))
    if university is None:
        return courseware.views.courses(request)

    return courseware.views.university_profile(request, university)


def auto_auth(request):
    """
    Automatically logs the anonymous user in with a generated random credentials
    This view is only accessible when settings.AUTOMATIC_AUTH_FOR_LOAD_TESTING is
    true.
    """

    from django.contrib.auth.models import User
    from django.contrib.auth import login, authenticate
    from random import randint

    # generate random user ceredentials from a small name space
    name_base = 'USER_'
    pass_base = 'PASS_'

    number = randint(1, settings.MAX_AUTO_AUTH_USERS)

    username = name_base + str(number)
    password = pass_base + str(number)

    # if they already are a user, log in 
    try:
        user = User.objects.get(username=username)
        user = authenticate(username=username, password=password)
        login(request, user)

    except:
        # create and activate account info
        student.views.create_account(request, username, password)
        request.user.is_active = True
        request.user.save()

    # redirect to home-page
    return redirect('root')
