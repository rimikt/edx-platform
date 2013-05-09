from external_auth.views import ssl_login_shortcut
from mitxmako.shortcuts import render_to_response
from django_future.csrf import ensure_csrf_cookie
from requests import index

"""
Public views
"""

@ensure_csrf_cookie
def signup(request):
    """
    Display the signup form.
    """
    csrf_token = csrf(request)['csrf_token']
    return render_to_response('signup.html', {'csrf': csrf_token})


def old_login_redirect(request):
    '''
    Redirect to the active login url.
    '''
    return redirect('login', permanent=True)


@ssl_login_shortcut
@ensure_csrf_cookie
def login_page(request):
    """
    Display the login form.
    """
    csrf_token = csrf(request)['csrf_token']
    return render_to_response('login.html', {
        'csrf': csrf_token,
        'forgot_password_link': "//{base}/#forgot-password-modal".format(base=settings.LMS_BASE),
    })


def howitworks(request):
    if request.user.is_authenticated():
        return index(request)
    else:
        return render_to_response('howitworks.html', {})

def ux_alerts(request):
    """
    static/proof-of-concept views
    """
    return render_to_response('ux-alerts.html', {})

