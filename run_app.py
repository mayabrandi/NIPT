# encoding: utf-8
#from database import  db
import os
#from views import app  
from flask import Flask
from werkzeug.contrib.fixers import ProxyFix

from flask_debugtoolbar import DebugToolbarExtension



def main():
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_pyfile('config.py')
    import PNIPT.views
    app.wsgi_app = ProxyFix(app.wsgi_app)
    
    #PNIPT.views.db.init_app(app)
    app.debug = True
    toolbar = DebugToolbarExtension(app)
    app.run(port=7072)    

if __name__ == "__main__":
    main()











