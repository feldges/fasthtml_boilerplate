from fasthtml.oauth import GoogleAppClient, OAuth
from fasthtml.common import FastHTML, RedirectResponse
from fasthtml.common import *

from dotenv import load_dotenv
import os
from datetime import datetime
load_dotenv()

try:
    with open('terms_of_service.md', 'r') as file:
        TERMS_OF_SERVICE = file.read()
except FileNotFoundError:
    TERMS_OF_SERVICE = "Terms of service file not found."

application_name = "Investment Reports App"
application_description = Div("""Generate teasers for any company, based on information collected on the internet.
                            This application is based on """, A("STORM", href = "https://storm.genie.stanford.edu/", target="_blank"), """, a framework developed by the Stanford University to generate Wiki pages.
                            It is experimental and may not work as expected.""")

headers = (MarkdownJS(), picolink, Favicon('favicon.ico', 'favicon.ico'))
app = FastHTML(hdrs=headers)

# ------------------------------------------------------------
# Database to track users and another entity
db = database('data/opportunity.db')
opportunity, user = db.t.opportunity, db.t.user
if opportunity not in db.t:
    user.create(id=str, email=str, first_name=str, last_name=str, terms_agreed=bool, terms_agreed_or_rejected_date=datetime, terms_agreed_date_first_time=datetime, pk='id')
    opportunity.create(id=str, name=str, user_id=str, pk='id')
# Create types for the database tables
Opportunity, User = opportunity.dataclass(), user.dataclass()

# Add a before to the app to limit access to the database
def restrict_db_access(req, session):
    auth = req.scope['auth']
    opportunity.xtra(user_id=auth)
    user.xtra(id=auth)
# ------------------------------------------------------------

# ------------------------------------------------------------
# Authentication via Google OAuth2
AUTH_CLIENT_ID = os.getenv("AUTH_CLIENT_ID")
AUTH_CLIENT_SECRET = os.getenv("AUTH_CLIENT_SECRET")

client = GoogleAppClient(
        AUTH_CLIENT_ID,
        AUTH_CLIENT_SECRET
        )

class Auth(OAuth):
    def get_auth(self, info, ident, session, state):
        email = info.email or ''
        if info.email_verified:
            try:
                u = user[ident]
            except NotFoundError:
                u = user.insert(id=ident, email=info.email, first_name=info.given_name, last_name=info.family_name)
            return RedirectResponse('/', status_code=303)
        return RedirectResponse(self.login_path, status_code=303)

oauth = Auth(app, client, skip=[r'/login', r'/redirect', r'/error', r'/favicon\.ico', r'/static/.*', r'.*\.css'])
# The db access restriction has to be added to the before list AFTER the OAuth authentication
app.before.append(Beforeware(restrict_db_access, skip=oauth.skip))

# This is needed to serve the favicon.ico file (and potentially other static files)
# If you use fast_app instead of FastHTML, this is not needed as this has been integrated in fast_app already
@app.get("/{fname:path}.{ext:static}")
def get(fname:str, ext:str): return FileResponse(f'{fname}.{ext}')
# ------------------------------------------------------------

# ------------------------------------------------------------
# FastHTML Application starts here

@app.get('/')
def home(auth):
    if not user[auth].terms_agreed:
        return Div(Div("You need to agree to the terms of service before you can use this application. Please read the terms of service and click the button to agree.", style="margin-top: 20px; margin-bottom: 20px;"),
        Div(TERMS_OF_SERVICE, cls='marked', style='border: 1px solid #ccc; border-radius: 8px; padding: 10px; margin-bottom: 20px;'),
        Div(
            "By clicking on 'Agree', I confirm that I have read and agree with the terms of service.",
            A('Agree', href='/agree_terms', role='button', style='margin-left: 10px;'),
            style='display: flex; flex-direction: row; align-items: center; justify-content: space-between; margin-bottom: 10px; width: 100%;')
        , style='display: flex; flex-direction: column; align-items: center; justify-content: center; width: 50%; margin: 0 auto;')

    return Div(
        H2(f"Welcome to the {application_name}, {user[auth].first_name} {user[auth].last_name}!"),
        A('Log out', href='/logout', role='button', style='margin-bottom: 10px;'),
        A('Remove approval terms of service', href='/agree_terms?approve=False', role='button', style='margin-bottom: 10px;'),
        style='display: flex; flex-direction: column; align-items: center; justify-content: center; height: 50vh;'
        )

@app.get('/login')
def login(req):
    return Div(
            H1(application_name),
            Div(application_description, style='margin-bottom: 20px; max-width: 30%; text-align: justify;'),
            A('Log in', href=oauth.login_link(req), role='button'),
            style='display: flex; flex-direction: column; align-items: center; justify-content: center; height: 50vh;'
            )

@app.get('/agree_terms')
def agree_terms(req, auth, approve: bool = None):
    approve = True if approve is None else approve
    user.update(id=auth, terms_agreed=approve, terms_agreed_or_rejected_date=datetime.now(), terms_agreed_date_first_time=datetime.now() if user[auth].terms_agreed_date_first_time is None else user[auth].terms_agreed_date_first_time)
    if approve:
        return RedirectResponse('/', status_code=303)
    else:
        return RedirectResponse('/logout', status_code=303)

serve(host='localhost', port=8000)
