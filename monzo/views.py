import datetime
import os

import requests
from django.middleware import csrf
from django.shortcuts import render, redirect
from django.urls import reverse

CLIENT_ID = os.environ.get('CLIENT_ID')
CLIENT_SECRET = os.environ.get('CLIENT_SECRET')

DATE_FORMAT = '%Y-%m-%d'
DATETIME_FORMAT = '%Y-%m-%dT%H:%M:%S.%fZ'


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

    # Get the since/before dates for fetching the transactions.
    date_calculator = MonthStartEndDateCalculator(request.GET.get('start'))

    # Load this month's transactions.
    transactions_response = _get_transactions(
        request,
        account_id,
        date_calculator.get_start_date(),
        date_calculator.get_end_date(),
    )
    transaction_list = _parse_transactions(transactions_response)

    # Get previous_since/next_since for the context
    return render(request, template_name='monzo/my-transactions.html', context={
        'transaction_list': transaction_list,
        'account_id': account_id,
        'previous_start': date_calculator.get_previous_month_start_date(),
        'next_start': date_calculator.get_next_month_start_date(),
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
class MonthStartEndDateCalculator(object):
    """
    Class for getting a start/end dates of a month.
    """
    def __init__(self, date=None):
        if date is None:
            self.date = datetime.datetime.now()
        else:
            self.date = datetime.datetime.strptime(date, DATE_FORMAT)

    def get_start_date(self):
        """
        Gets the first day of the current self.date month.
        """
        return self.date.replace(day=1)

    def get_end_date(self):
        """
        Gets the last day of the current self.date month.
        """
        return (self.get_start_date() + datetime.timedelta(32)).replace(day=1)

    def get_previous_month_start_date(self):
        """
        Gets the date of the first day of the previous month.
        """
        previous_start = self.date.replace(day=1) - datetime.timedelta(1)
        return previous_start.replace(day=1).date().strftime(DATE_FORMAT)

    def get_next_month_start_date(self):
        """
        Gets the date of the first day of the next month.
        """
        next_start = self.date.replace(day=1) + datetime.timedelta(32)
        return next_start.replace(day=1).date().strftime(DATE_FORMAT)


def _get_redirect_uri():
    return '%s%s' % ('http://localhost:8000', reverse('monzo:login_callback'))


def _test_monzo_access_token_in_session(request):
    return 'monzo_access_token' in request.session


def _get_transactions(request, account_id, start, end):
    auth_token = request.session['monzo_access_token']
    return requests.get(
        'https://api.monzo.com/transactions',
        data={
            'account_id': account_id,
            'since': start.date(),
            'before': end.date(),
        },
        headers={"Authorization": "Bearer %s" % auth_token}
    )


def _parse_transactions(response):
    transaction_list = response.json().get('transactions')
    # Remove transactions that are not negative.
    transaction_list = [t for t in transaction_list if t.get('amount') < 0]
    # Only return the bits we need.
    return [
        {
            'description': transaction.get('description'),
            'notes': transaction.get('notes'),
            # Make all transaction values positive and add 2 decimal points.
            'amount': -1 * float(transaction.get('amount')) / 100,
            'created': datetime.datetime.strptime(transaction.get('created'), DATETIME_FORMAT),
        }
        for transaction in transaction_list
    ]
