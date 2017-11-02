from flask.ext.mail import Mail
from flask.ext.login import LoginManager
from flask_oauthlib.client import OAuth
from PNIPT import app
#import ssl

#ctx = ssl.SSLContext(ssl.PROTOCOL_SSLv23)

mail = Mail(app)
login_manager = LoginManager(app)
oauth = OAuth(app)
google = oauth.remote_app('google', app_key='GOOGLE')
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access this page.'
login_manager.refresh_view = 'reauth'




