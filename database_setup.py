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




class NiptDBSetup():

    def __init__(self, nipt_db):
        self.db = nipt_db
        self.batch_id = None 
	self.date = None
	self.flowcell = None


    def get_run_folder_info(self, folder_path):
        f_name_info = folder_path.split('/')[-2].split('_')
        self.batch_id = f_name_info[2]
        self.date = f_name_info[0]
        self.flowcell = f_name_info[3]

    def update_nipt_db(self, csv_file_path):
        nipt_results = self.parse_path(csv_file_path)
        self.get_run_folder_info(nipt_results)
        reader = csv.DictReader(open(nipt_results, 'rb'))
        batch = Batch.query.filter_by(batch_id = self.batch_id).first()
        if not batch:
            batch = Batch(self.batch_id, self.date, self.flowcell)
            self.db.session.add(batch)
        for row in reader:
            sample = Sample.query.filter_by(sample_ID = row['SampleID']).first()
            if not sample:
                sample = Sample(row, batch)
                self.db.session.add(sample)
                cov = Coverage(row, sample, batch)
                self.db.session.add(cov)
                ncv = NCV(row, sample, batch)
                self.db.session.add(ncv)
            if not batch:
                batchstat = BatchStat(row, batch)
                self.db.session.add(batchstat)
        try:
            self.db.session.commit()
        except:
            error = sys.exc_info()
            logging.error('error in update_nipt_db!!!!!!!')
            logging.error(error)
            pass


    def set_batch_id_from_sample_sheet(self, sample_sheet):
	sample_sheet = self.parse_path(sample_sheet)
	self.get_run_folder_info(sample_sheet)
        sheet = open(sample_sheet, 'rb')
        for l in sheet:
            if 'Investigator Name' in l:
                try:
                    investigator_name = l.split(',')[1].split('_')
                    batch_name = '_'.join(investigator_name[0:2])
                    batch = Batch.query.filter_by(batch_id = self.batch_id).first()
                    batch.batch_name = batch_name
                    self.db.session.add(batch)
                    self.db.session.commit()
                except:
                    pass


    def parse_path(self, path):
        if glob.glob(path):
            return glob.glob(path)[0]
        else:
            return None


def main(csv_files, users_file, sample_sheets):
    db.init_app(app)
    logging.basicConfig(filename = 'NIPT_database_log', level=logging.DEBUG)
    db.engine.execute("SET foreign_key_checks = 0")
    db.create_all()
    db.engine.execute("SET foreign_key_checks = 1")
    if users_file:
        users_data = open(users_file)
        users = json.load(users_data)
        db.create_all()
        for usr, inf in users.items():
            in_db = User.query.filter_by(email = inf['Email']).first()
            if not in_db:
                in_db = User.query.filter_by(email = inf['Email']).first()
                user = User(inf['Email'],inf['Name'])
                db.session.add(user)
                db.session.commit()
    for path in csv_files:
        try:
            csv_path = path.rstrip('/')
            NDBS = NiptDBSetup(db)
            NDBS.get_run_folder_info(csv_path)
            if NDBS.batch_id:
                NDBS.update_nipt_db(csv_path)
            else:
                logging.warning("Could not add to database from resultfile: %s" % path)
        except:
            logging.warning("Issues getting info from resultfile: %s" % path)
            pass
    for path in sample_sheets:
        try:
            path = path.rstrip('/')
            NDBS = NiptDBSetup(db)
            NDBS.get_run_folder_info(path)
            if NDBS.batch_id:
                NDBS.set_batch_id_from_sample_sheet(path)
            else:
                logging.warning("Could not add batch name to database from sample sheet: %s" % path)
        except:
            logging.warning("Could not get batch name from sample sheet: %s" % path)
            pass


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
    parser.add_argument('--csv_files', nargs='+', default = [], dest = 'csv', 
                    help ='List of paths to NIPT csv resultfiles.')
    parser.add_argument('--sample_sheets', nargs='+', default = [], dest = 'sheets',
                    help = 'List of pathes to NIPT sample_sheets.')
    parser.add_argument('--users', default = None, dest = 'users', 
                    help = 'json file with Users')

    args = parser.parse_args()

    main(args.csv, args.users, args.sheets)



