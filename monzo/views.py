import os

import requests
from django.middleware import csrf
from django.shortcuts import render, redirect
from django.urls import reverse

CLIENT_ID = os.environ.get('CLIENT_ID')
CLIENT_SECRET = os.environ.get('CLIENT_SECRET')


def home(request):
    """
    Home page with a link to login.
    """
    return render(request, template_name='monzo/home.html')


def my_accounts(request):
    """
    Show all the user accounts.
    """
    if not _test_monzo_access_token_in_session(request):
        return redirect(reverse('monzo:home'))

    auth_token = request.session['monzo_access_token']

    response = requests.get(
        'https://api.monzo.com/accounts',
        headers={"Authorization":"Bearer %s" % auth_token}
    )

    return render(request, template_name='monzo/my-accounts.html', context={
        'account_list': response.json().get('accounts')
    })


def my_transactions(request, account_id):
    """
    Show a list of transactions for the selected account_id.
    """
    if not _test_monzo_access_token_in_session(request):
        return redirect(reverse('monzo:home'))

    auth_token = request.session['monzo_access_token']

    # Load a few transactions.
    response = requests.get(
        'https://api.monzo.com/transactions',
        data={
            'account_id': account_id,
        },
        headers={"Authorization": "Bearer %s" % auth_token}
    )

    return render(request, template_name='monzo/my-transactions.html', context={
        'transaction_list': response.json().get('transactions'),
        'account_id': account_id
    })

####################
# Auth views
####################

def login(request):
    """
    Redirect the user to the monzo login screen.
    """
    request.session['csrf_token'] = csrf.get_token(request)
    url = "https://auth.monzo.com/?client_id=%s&redirect_uri=%s&response_type=code&state=%s" % (
        CLIENT_ID,
        _get_redirect_uri(),
        request.session['csrf_token']
    )
    return redirect(url)


def login_callback(request):
    """
    Callback from Monzo. Should contain an access code and a state.
    """
    # Verify the returned state matches the session csrf token.
    if 'csrf_token' not in request.session or request.GET.get('state') != request.session['csrf_token']:
        redirect(reverse('monzo:home'))

    # If it's all good, get the access token.
    response = requests.post('https://api.monzo.com/oauth2/token', data={
        'grant_type': 'authorization_code',
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET,
        'redirect_uri': _get_redirect_uri(),
        'code': request.GET.get('code'),
    })
    if response.status_code == 200:
        request.session['monzo_access_token'] = response.json().get('access_token')
        return redirect(reverse('monzo:my_accounts'))

    return redirect(reverse('monzo:home'))


####################
# Helpers
####################


def _get_redirect_uri():
    return '%s%s' % ('http://127.0.0.1:8000', reverse('monzo:login_callback'))


def _test_monzo_access_token_in_session(request):
    return 'monzo_access_token' in request.session
