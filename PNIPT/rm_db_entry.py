#!/user/bin/env python
DESC="""Script to delet a batch from the database.
Run the script and  

Written by Maya Brandi"""
import logging
from argparse import ArgumentParser
from database import db, Batch, NCV, Coverage, Sample, User ,BatchStat

logging.basicConfig(datefmt='%m/%d/%Y %I:%M:%S %p', filename = 'delete_db_entry.log', level=logging.DEBUG)
# define a Handler which writes INFO messages or higher to the sys.stderr
console = logging.StreamHandler()
console.setLevel(logging.INFO)
# set a format which is simpler for console use
formatter = logging.Formatter('%(name)-12s: %(levelname)-8s %(message)s')
# tell the handler to use this format
console.setFormatter(formatter)
# add the handler to the root logger
logging.getLogger('').addHandler(console)

def remove_batch(batch_id):
    db_entries = NCV.query.filter_by(batch_id = batch_id).all()
    db_entries += Coverage.query.filter_by(batch_id = batch_id).all()
    db_entries += Sample.query.filter_by(batch_id = batch_id).all()
    db_entries += BatchStat.query.filter_by(batch_id = batch_id).all()
    db_entries += Batch.query.filter_by(batch_id = batch_id).all()
    for enty in db_entries:
        db.session.delete(enty) 
    db.session.commit()

def validation(batch_id):
    check_dict = {'ncv_entries' :NCV.query.filter_by(batch_id = batch_id).all(),
    'coverage_entries' :  Coverage.query.filter_by(batch_id = batch_id).all(),
    'sample_entries' : Sample.query.filter_by(batch_id = batch_id).all(),
    'batch_stat_entries' : BatchStat.query.filter_by(batch_id = batch_id).all(),
    'batch_entries' : Batch.query.filter_by(batch_id = batch_id).all()}
    for key, val in check_dict.items():
        if val:
            logging.warning( key + ' were not deleted from the database')
        else:
            logging.info( key + ' were properly deleted from the database')
        
    

def main(batch_ids):
    for batch_id in batch_ids:
        remove_batch(batch_id)
        validation(batch_id)
    
if __name__ == '__main__':
    parser = ArgumentParser(description=DESC)
    parser.add_argument('-b',  nargs='+', default = [] , dest = 'Flowcell_id', 
                    help = 'List of flocell ids. Eg: AH3FMNADXY BH3FKLADXY AH2YNTADXY')
    args = parser.parse_args()
    main(args.Flowcell_id)



