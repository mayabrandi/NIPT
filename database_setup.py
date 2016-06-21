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

    def get_run_folder_info(self, folder):
        print folder
        f_name_info = folder.split('_')
        self.batch_id = f_name_info[3]
        self.date = f_name_info[0]
        self.flowcell = f_name_info[3]

    def update_nipt_db(self, folder):
        nipt_results = app.config.get('ANALYSIS_PATH') + folder + '*/*NIPT_RESULTS.csv'
        sample_sheet = app.config.get('RUN_FOLDER_PATH') + folder + '/SampleSheet.csv'
        nipt_results = self.parse_path(nipt_results)
        sample_sheet = self.parse_path(sample_sheet)
        batch = Batch.query.filter_by(batch_id = self.batch_id).first()
        if sample_sheet and not batch:
            self.get_batch_name_from_sample_sheet(sample_sheet)
            if self.batch_name:
                batch = Batch(self.batch_id, self.date, self.flowcell)
                batch.batch_name = self.batch_name
                self.db.session.add(batch)
                self.db.session.commit()
        print nipt_results
        print sample_sheet
        print self.batch_name
        if nipt_results and self.batch_name:
            reader = csv.DictReader(open(nipt_results, 'rb'))
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
            logging.warning("Could not get analysis info from file: %s" % nipt_results)
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
                    logging.exception("Could not get batch name from sample sheet: %s" % path)
                    pass

    def parse_path(self, path):
        if glob.glob(path):
            return glob.glob(path)[0]
        else:
            return None

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

def main(run_folders, users_file):
    db.init_app(app)
    logging.basicConfig(filename = 'NIPT_database_log', level=logging.DEBUG)
    db.create_all()
    NDBS = NiptDBSetup(db)
    NDBS.set_users(users_file)

    for folder in run_folders:
        BM = BatchMaker(db)
        BM.get_run_folder_info(folder)
        if BM.batch_id:
            BM.update_nipt_db(folder)
        else:
            logging.warning("Could not add to database from resultfile: %s" % path)


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
    parser.add_argument('--run_folders', nargs='+', default = [], dest = 'run_folders',
                    help ='List of run folder names. Format example: 160511_D00410_0245_AH23VMADXY')
    parser.add_argument('--users', default = None, dest = 'users',
                    help = 'json file with Users')

    args = parser.parse_args()

    main(args.run_folders, args.users)


