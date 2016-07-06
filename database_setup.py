#!/user/bin/env python
DESC="""Script to set up the NIPT-database. Fetching info from sample sheets 
for sequencing, NIPT analysisi results from ...??? 

Written by Maya Brandi"""

from argparse import ArgumentParser
import json
import csv
import logging
import os
import sys
import glob
from extentions import app
from database import db, Batch, NCV, Coverage, Sample, User ,BatchStat

class BatchMaker():

    def __init__(self, nipt_db):
        self.db = nipt_db
        self.batch_id = None
        self.batch_name = None
        self.date = None
        self.flowcell = None
        self.nipt_results = None
        self.sample_sheet = None


    def get_run_folder_info(self):
        try:
            print self.sample_sheet
            folder = self.sample_sheet.split('/')[-2] 
            f_name_info = folder.split('_')
            self.batch_id = f_name_info[3]
            self.date = f_name_info[0]
            self.flowcell = f_name_info[3]
        except:
            pass

    def update_nipt_db(self):
        batch = Batch.query.filter_by(batch_id = self.batch_id).first()
        if self.sample_sheet and not batch:
            self.get_batch_name_from_sample_sheet(self.sample_sheet)
            if self.batch_name:
                batch = Batch(self.batch_id, self.date, self.flowcell)
                batch.batch_name = self.batch_name
                self.db.session.add(batch)
                self.db.session.commit()
        if self.nipt_results and self.batch_name:
            reader = csv.DictReader(open(self.nipt_results, 'rb'))
            for row in reader:
                sample = Sample.query.filter_by(sample_ID = row['SampleID']).first()
                if not sample:
                    sample = Sample(row, batch)
                    self.db.session.add(sample)
                    cov = Coverage(row, sample, batch)
                    self.db.session.add(cov)
                    ncv = NCV(row, sample, batch)
                    self.db.session.add(ncv)
                    batchstat = BatchStat(row, batch)
                    self.db.session.add(batchstat)
        else:
            logging.warning("Could not get analysis info from file: %s" % self.nipt_results)
        try:
            self.db.session.commit()
        except: 
            error = sys.exc_info()
            logging.exception('error in update_nipt_db!!!!!!!')
            logging.error(error)
            pass

    def get_batch_name_from_sample_sheet(self, path):
        sheet = open(path, 'rb')
        for l in sheet:
            if 'Investigator Name' in l:
                try:
                    investigator_name = l.split(',')[1].split('_')
                    self.batch_name = '_'.join(investigator_name[0:2])
                except:
                    logging.exception("Could not get batch name from sample sheet: %s" %path)
                    pass

    def parse_path(self, flowcell_id):
        nipt_results = app.config.get('ANALYSIS_PATH') +'*' + flowcell_id + '*/*NIPT_RESULTS.csv'
        sample_sheet = app.config.get('RUN_FOLDER_PATH')+'*' + flowcell_id + '*/SampleSheet.csv'        
        if glob.glob(nipt_results) and glob.glob(sample_sheet):
            self.nipt_results = glob.glob(nipt_results)[0]
            self.sample_sheet = glob.glob(sample_sheet)[0]


class NiptDBSetup():
    def __init__(self, nipt_db):
        self.db = nipt_db

    def set_users(self, users_file):
        if users_file:
            users_data = open(users_file)
            users = json.load(users_data)
            self.db.create_all()
            for usr, inf in users.items():
                in_db = User.query.filter_by(email = inf['Email']).first()
                if not in_db:
                    in_db = User.query.filter_by(email = inf['Email']).first()
                    user = User(inf['Email'],inf['Name'])
                    self.db.session.add(user)
                    self.db.session.commit()

def main(flowcell_ids, users_file):
    db.init_app(app)
    logging.basicConfig(filename = 'NIPT_database_log', level=logging.DEBUG)
    db.create_all()
    NDBS = NiptDBSetup(db)
    NDBS.set_users(users_file)

    for flowcell_id in flowcell_ids:
        BM = BatchMaker(db)
        BM.parse_path(flowcell_id)
        BM.get_run_folder_info()
        print BM.batch_id
        if BM.batch_id:
            BM.update_nipt_db()
        else:
            logging.warning("Could not add to database from run: %s" % flowcell_id)


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



if __name__ == '__main__':
    parser = ArgumentParser(description=DESC)
    parser.add_argument('--flowcell_ids', nargs='+', default = [], dest = 'flowcell_ids',
                    help ='List of run flowcell ids. Format example: AH23VMADXY')
    parser.add_argument('--users', default = None, dest = 'users',
                    help = 'json file with Users')

    args = parser.parse_args()

    main(args.flowcell_ids, args.users)


