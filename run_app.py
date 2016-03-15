# encoding: utf-8
from database import  db
from extentions import ssl, ctx
import logging
import os
from views import app  


logging.basicConfig(datefmt='%m/%d/%Y %I:%M:%S %p', filename = 'NIPT_log', level=logging.DEBUG)
# define a Handler which writes INFO messages or higher to the sys.stderr
console = logging.StreamHandler()
console.setLevel(logging.INFO)
# set a format which is simpler for console use
formatter = logging.Formatter('%(name)-12s: %(levelname)-8s %(message)s')
# tell the handler to use this format
console.setFormatter(formatter)
# add the handler to the root logger
logging.getLogger('').addHandler(console)


def main():
    ssl(app)
    db.init_app(app)
    app.run(ssl_context = ctx, host='0.0.0.0', port=8082)    

if __name__ == "__main__":
    main()


