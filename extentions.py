from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask.ext.mail import Mail
from argparse import ArgumentParser
import json
import csv
import logging
import sys
import glob
from flask.ext.login import LoginManager
from flask_oauthlib.client import OAuth
from flask_sslify import SSLify
from OpenSSL import SSL

# (ext lacks init_app...)
ctx = SSL.Context(SSL.SSLv23_METHOD)

def ssl(app):
    # Setup SSL: http://flask.pocoo.org/snippets/111/
    ctx.use_privatekey_file(app.config.get('SSL_KEY_PATH'))
    ctx.use_certificate_file(app.config.get('SSL_CERT_PATH'))

    # https://github.com/kennethreitz/flask-sslify
    # Force SSL. Redirect all incoming requests to HTTPS.
    # Only takes effect when DEBUG=False
    return SSLify(app)



app = Flask(__name__)
app.config.from_pyfile('../../config/config.py')
mail = Mail(app)

login_manager = LoginManager(app)
oauth = OAuth(app)

        # use Google as remote application
        # you must configure 3 values from Google APIs console
        # https://code.google.com/apis/console
google = oauth.remote_app('google', app_key='GOOGLE')
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access this page.'
login_manager.refresh_view = 'reauth'




