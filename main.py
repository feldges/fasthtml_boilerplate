from fasthtml.oauth import GoogleAppClient, OAuth
from fasthtml.common import FastHTML, RedirectResponse
from fasthtml.common import *

from fastsql import Database
from fastsql.core import _type_map, NotFoundError as postgresql_NotFoundError

from dotenv import load_dotenv
import os
from datetime import datetime
from sqlalchemy import DateTime
from copy import deepcopy

load_dotenv()

# Extend type_map before creating tables
_type_map[datetime] = DateTime  # Add datetime support

# ------------------------------------------------------------
# Configuration
try:
    with open('assets/legal/terms_of_service.md', 'r') as file:
        TERMS_OF_SERVICE = file.read()
except FileNotFoundError:
    TERMS_OF_SERVICE = "Terms of service file not found."

try:
    with open('assets/legal/privacy_policy.md', 'r') as file:
        PRIVACY_POLICY = file.read()
except FileNotFoundError:
    PRIVACY_POLICY = "Privacy policy file not found."

application_name = "Investment Reports App"
application_description = Div("""Generate teasers for any company, based on information collected on the internet.
                            This application is based on """, A("STORM", href = "https://storm.genie.stanford.edu/", target="_blank"), """, a framework developed by the Stanford University to generate Wiki pages.
                            It is experimental and may not work as expected.""")
application_description_txt = """Generate teasers for any company, based on information collected on the internet. This application is based on "STORM", a framework developed by the Stanford University to generate Wiki pages. It is experimental and may not work as expected."""

socials = Socials(title=application_name, description=application_description_txt, site_name='storm.aipe.tech', image='https://storm.aipe.tech/assets/images/investment_analyzer_screen.png', url='https://storm.aipe.tech')

app_styles = """
.dropdown {
    position: relative;
    cursor: pointer;
    width: 24px;
    height: 24px;
}

#menu-container {
    position: absolute;
    right: 0;
    top: 100%;
}

.dropdown-menu {
    position: relative;  /* Changed from absolute since it's inside container */
    background: white;
    border: 1px solid #ddd;
    border-radius: 4px;
    box-shadow: 0 2px 5px rgba(0,0,0,0.1);
    min-width: 200px;
    padding-top: 8px;
    margin-top: 5px;  /* Add space between initials and menu */
    z-index: 1001;
}

.menu-underlay {
    position: fixed;  /* Changed to fixed */
    top: 0;
    bottom: 0;
    left: 0;
    right: 0;
    z-index: 1000;
}

.dropdown-menu a {
    display: block;
    padding: 8px 16px;
    text-decoration: none;
    color: black;
}

.dropdown-menu a:hover {
    background-color: #f5f5f5;
}
"""

headers = (MarkdownJS(), Style(app_styles), socials, picolink, Favicon('assets/images/favicon.ico', 'assets/images/favicon.ico'))
app = FastHTML(title=application_name, hdrs=headers)
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
    db = Database(db_url)
else:
    raise ValueError(f"Invalid database type: {db_type}")

users = db.create(Users, pk='id')
opportunities = db.create(Opportunities, pk='id')

# Add a before to the app to limit access to the database
def restrict_db_access(req, session):
    auth = req.scope['auth']
    opportunities.xtra(user_id=auth)
    users.xtra(id=auth)

# Add a before to the app to check if the user has agreed to the terms of service
def check_terms_agreed(req, session):
    auth = session.get('auth')
    print("Auth", auth)
    print(users[auth].terms_agreed)
    if not users[auth].terms_agreed:
        return RedirectResponse('/terms_of_service', status_code=303)
    return None
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

oauth = Auth(app, client, skip=[r'/login', r'/redirect', r'/error', r'/logout', r'/privacy_policy', r'/terms_of_service', r'/favicon\.ico', r'/static/.*', r'/assets/.*', r'.*\.css'])
# The db access restriction has to be added to the before list AFTER the OAuth authentication
app.before.append(Beforeware(restrict_db_access, skip=oauth.skip))
skip_list_check_terms = deepcopy(oauth.skip)
skip_list_check_terms.append(r'/agree_terms')
app.before.append(Beforeware(check_terms_agreed, skip=skip_list_check_terms))

# This is needed to serve the favicon.ico file (and potentially other static files)
# If you use fast_app instead of FastHTML, this is not needed as this has been integrated in fast_app already
@app.get("/{fname:path}.{ext:static}")
def get(fname:str, ext:str): return FileResponse(f'{fname}.{ext}')
# ------------------------------------------------------------

# ------------------------------------------------------------
# FastHTML Application starts here

# Handler for toggle_menu endpoint
@app.get('/toggle_menu')
def toggle_menu():
    global show_menu
    show_menu = not show_menu
    if show_menu:
        return Div(
            # First div is the underlay for catching clicks
            Div(
                cls='menu-underlay',
                hx_get='/hide_menu',
                hx_target='#menu-container',
                hx_swap='outerHTML'
            ),
            # Second div is the menu content
            Div(
                A('Terms of Service', href='/terms_of_service'),
                A('Privacy Policy', href='/privacy_policy'),
                A('Log out', href='/logout'),
                cls='dropdown-menu'
            ),
            id='menu-container'
        )
    else:
        return Div(id='menu-container')

@app.get('/hide_menu')
def hide_menu():
    global show_menu
    show_menu = not show_menu
    return Div(id='menu-container')

@app.get('/login')
def login(req):
    return Title("Login"), login_header(), Div(
            H1(application_name),
            Div(application_description, style='margin: 0 auto 10px auto; width: 100%; max-width: 600px; text-align: justify; padding: 0 20px;'),
            Div(
                A(
                    Img(src='/assets/images/google-logo.svg',
                        style='''
                            cursor: pointer;
                            transition: all 0.2s ease;
                            border: 1px solid #ddd;
                            border-radius: 4px;
                        ''',
                        onmouseover="this.style.transform='translateY(-3px) scale(1.05)'; this.style.filter='drop-shadow(0 4px 6px rgba(0,0,0,0.1))'",
                        onmouseout="this.style.transform='translateY(0) scale(1)'; this.style.filter='none'"
                    ),
                    href=oauth.login_link(req)
                ),
                style='display: flex; justify-content: center; margin: 20px 0;'
            ),
            Div(
                Div(
                    A('Terms of Service', href='/terms_of_service', target='_blank'),
                    style='flex: 1; display: flex; justify-content: center; font-size: 0.8rem;'
                ),
                Div(
                    A('Privacy Policy', href='/privacy_policy', target='_blank'),
                    style='flex: 1; display: flex; justify-content: center; font-size: 0.8rem;'
                ),
                style='margin-top: 20px; display: flex; width: 100%; max-width: 600px;'
            ),
            style='display: flex; flex-direction: column; align-items: center; justify-content: center; height: 50vh;'
            )

@app.get('/terms_of_service')
def terms_of_service(req, session):
    if 'show_menu' in globals():
        show_menu = False
        # trigger htmx to hide the menu
    auth = session.get('auth')
    preamble = Div("")
    button = Div("")
    if auth:
        if users[auth].terms_agreed:
            preamble = Div(
                "You have already agreed to the terms of service. If you want to remove your approval, click on the button below.",
                style="margin-bottom: 20px;"
            )
            button = Div(
                "By clicking on 'Remove approval', I confirm that I want to remove my approval of the terms of service. As a consequence, I will not be able to use this application anymore.",
                A('Remove approval', href='/agree_terms?approve=False', role='button', style='margin-left: 10px;'),
                style='display: flex; flex-direction: row; align-items: center; justify-content: space-between; margin-top: 20px; width: 100%;'
            )
        else:
            preamble = Div(
                "You need to agree to the terms of service before you can use this application. Please read the terms of service and click the button to agree.",
                style="margin-bottom: 20px;"
            )
            button = Div(
                "By clicking on 'Agree', I confirm that I have read and agree with the terms of service.",
                A('Agree', href='/agree_terms', role='button', style='margin-left: 10px;'),
                style='display: flex; flex-direction: row; align-items: center; justify-content: space-between; margin-top: 20px; width: 100%;'
            )

    return Title("Terms of Service"), Div(
        Div(
            preamble,
            Div(
                TERMS_OF_SERVICE,
                cls='marked',
                style='border: 1px solid #ccc; border-radius: 8px; padding: 20px; max-width: 800px; font-size: 0.9em;'
            ),
            button,
            style='max-width: 800px;'
        ),
        style='display: flex; justify-content: center; align-items: start; min-height: 100vh; padding: 40px 20px;'
    )

@app.get('/privacy_policy')
def privacy_policy():
        return Title("Privacy Policy"), Div(
            Div(
                PRIVACY_POLICY,
                cls='marked',
                style='border: 1px solid #ccc; border-radius: 8px; padding: 20px; max-width: 800px; font-size: 0.9em;'
            ),
            style='display: flex; justify-content: center; align-items: start; min-height: 100vh; padding: 40px 20px;'
        )

@app.get('/agree_terms')
def agree_terms(req, session, approve: bool = None):
    auth = session.get('auth')
    print("Auth in agree_terms", auth)
    approve = True if approve is None else approve
    users.update(id=auth, terms_agreed=approve, terms_agreed_or_rejected_date=datetime.now(), terms_agreed_date_first_time=datetime.now() if users[auth].terms_agreed_date_first_time is None else users[auth].terms_agreed_date_first_time)
    if approve:
        return RedirectResponse('/', status_code=303)
    else:
        return RedirectResponse('/logout', status_code=303)

def login_header():
   return Div(
       Div(
           # Logo on the far left
           A(
               Img(
                   src='/assets/images/aipe_logo_white.svg',
                   alt='AIPE Logo',
                   style='height: 24px; width: auto;'
               ),
               href='/',
               style='text-decoration: none; margin-left: 20px;'
           ),
           style='display: flex; justify-content: space-between; align-items: center; padding: 6px 0; width: 100%;'
       ),
       style='border-bottom: 1px solid #0055a4; background: #0055a4; width: 100%;'
   )

# Create the header for the application
show_menu = False
def app_header(user):
    initials = f"{user.first_name[0]}{user.last_name[0]}"
    return Div(
        Div(
            # Logo on the far left
            A(
                Img(
                    src='/assets/images/aipe_logo_white.svg',
                    alt='AIPE Logo',
                    style='height: 24px; width: auto;'
                ),
                href='/',
                style='text-decoration: none; margin-left: 20px;'
            ),
            # Profile menu
            Div(
                # Initials circle with toggle behavior
                Div(
                    initials,
                    style='width: 24px; height: 24px; background: white; color: #0055a4; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 0.9rem; position: relative;',
                    hx_get='/toggle_menu',
                    hx_target='#menu-container',
                    hx_swap='outerHTML transition:true'
                ),
                # Menu container - keep it simple
                Div(id='menu-container'),
                cls='dropdown',
                style='margin-right: 20px;'
            ),
            style='display: flex; justify-content: space-between; align-items: center; padding: 6px 0; width: 100%;'
        ),
        style='border-bottom: 1px solid #0055a4; background: #0055a4; width: 100%;'
    )

# ------------------------------------------------------------
# This is where the real application starts

@app.get('/')
def home(auth):
    return Title(application_name), app_header(users[auth]), Div(
        H2(f"Welcome to the {application_name}, {users[auth].first_name} {users[auth].last_name}!"),
        P("This is where you can build your application"),
        style='display: flex; flex-direction: column; align-items: center; justify-content: center; height: 50vh;'
        )

if __name__ == "__main__":
    serve(host='localhost', port=8000)
