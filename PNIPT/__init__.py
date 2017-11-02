from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask.ext.mail import Mail
from flask.ext.login import LoginManager
from flask_oauthlib.client import OAuth
from flask_sslify import SSLify
import ssl
from werkzeug.contrib.fixers import ProxyFix
from flask_debugtoolbar import DebugToolbarExtension


app = Flask(__name__, instance_relative_config=True)
app.config.from_pyfile('config.py')

import PNIPT.views

app.wsgi_app = ProxyFix(app.wsgi_app)



# the toolbar is only enabled in debug mode:
app.debug = True

# set a 'SECRET_KEY' to enable the Flask session cookies
#app.config['RECORD_QUERIES'] = True
toolbar = DebugToolbarExtension(app)
