from fasthtml.oauth import GoogleAppClient, OAuth
from fasthtml.common import FastHTML, RedirectResponse
from fasthtml.common import *

from fastsql import Database
from fastsql.core import _type_map, NotFoundError as postgresql_NotFoundError

from dotenv import load_dotenv
import os
from datetime import datetime
from sqlalchemy import DateTime

load_dotenv()

# Extend type_map before creating tables
_type_map[datetime] = DateTime  # Add datetime support

# ------------------------------------------------------------
# Configuration
try:
    with open('terms_of_service.md', 'r') as file:
        TERMS_OF_SERVICE = file.read()
except FileNotFoundError:
    TERMS_OF_SERVICE = "Terms of service file not found."

application_name = "Investment Reports App"
application_description = Div("""Generate teasers for any company, based on information collected on the internet.
                            This application is based on """, A("STORM", href = "https://storm.genie.stanford.edu/", target="_blank"), """, a framework developed by the Stanford University to generate Wiki pages.
                            It is experimental and may not work as expected.""")
application_description_txt = """Generate teasers for any company, based on information collected on the internet. This application is based on "STORM", a framework developed by the Stanford University to generate Wiki pages. It is experimental and may not work as expected."""

socials = Socials(title=application_name, description=application_description_txt, site_name='storm.aipe.tech', image='assets/images/investment_analyzer_screen.png', url='https://storm.aipe.tech')

headers = (MarkdownJS(), socials, picolink, Favicon('assets/images/favicon.ico', 'assets/images/favicon.ico'))
app = FastHTML(hdrs=headers)
# ------------------------------------------------------------

# ------------------------------------------------------------
# Define datamodels and Database
class Users:
    id: str
    email: str
    first_name: str
    last_name: str
    terms_agreed: bool
    terms_agreed_or_rejected_date: datetime
    terms_agreed_date_first_time: datetime
class Opportunities:
    id: str
    name: str
    user_id: str

# Database can be either sqlite (small projects, local) or postgresql (large projects, cloud with multiple pods)
db_type = os.getenv("DB_TYPE", "sqlite")
db_file = os.getenv("DB_FILE", "data/opportunities.db")
db_url = os.getenv("DB_URL", "")

if db_type == "sqlite":
    db = database(db_file)
elif db_type == "postgresql":
    db = Database('postgresql://claude@localhost:5432/postgres')
else:
    raise ValueError(f"Invalid database type: {db_type}")

users = db.create(Users, pk='id')
opportunities = db.create(Opportunities, pk='id')

# Add a before to the app to limit access to the database
def restrict_db_access(req, session):
    auth = req.scope['auth']
    opportunities.xtra(user_id=auth)
    users.xtra(id=auth)
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
                u = users[ident]
            except (NotFoundError, postgresql_NotFoundError):
                u = users.insert(Users(id=ident, email=info.email, first_name=info.given_name, last_name=info.family_name))
            return RedirectResponse('/', status_code=303)
        return RedirectResponse(self.login_path, status_code=303)

oauth = Auth(app, client, skip=[r'/login', r'/redirect', r'/error', r'/favicon\.ico', r'/static/.*', r'/assets/.*', r'.*\.css'])
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
    if not users[auth].terms_agreed:
        return Div(Div("You need to agree to the terms of service before you can use this application. Please read the terms of service and click the button to agree.", style="margin-top: 20px; margin-bottom: 20px;"),
        Div(TERMS_OF_SERVICE, cls='marked', style='border: 1px solid #ccc; border-radius: 8px; padding: 10px; margin-bottom: 20px;'),
        Div(
            "By clicking on 'Agree', I confirm that I have read and agree with the terms of service.",
            A('Agree', href='/agree_terms', role='button', style='margin-left: 10px;'),
            style='display: flex; flex-direction: row; align-items: center; justify-content: space-between; margin-bottom: 10px; width: 100%;')
        , style='display: flex; flex-direction: column; align-items: center; justify-content: center; width: 50%; margin: 0 auto;')

    return Div(
        H2(f"Welcome to the {application_name}, {users[auth].first_name} {users[auth].last_name}!"),
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
    users.update(id=auth, terms_agreed=approve, terms_agreed_or_rejected_date=datetime.now(), terms_agreed_date_first_time=datetime.now() if users[auth].terms_agreed_date_first_time is None else users[auth].terms_agreed_date_first_time)
    if approve:
        return RedirectResponse('/', status_code=303)
    else:
        return RedirectResponse('/logout', status_code=303)

if __name__ == "__main__":
    serve(host='localhost', port=8000)
