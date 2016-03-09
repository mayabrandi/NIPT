# encoding: utf-8
from database import  db
from extentions import ssl, ctx
import logging
import os
from views import app  




def main():
    ssl(app)
    db.init_app(app)
    logging.basicConfig(filename = 'NIPT_log', level=logging.INFO)
    app.run(ssl_context = ctx, host='0.0.0.0', port=8082)    

if __name__ == "__main__":
    main()


