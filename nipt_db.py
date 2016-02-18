from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from argparse import ArgumentParser
import csv
import logging
import sys
import glob

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:////tmp/new_nipt.db'
db = SQLAlchemy(app)

class Sample(db.Model):
    __table_name__ = 'sample'
    id = db.Column(db.Integer, primary_key = True)
    batch_id = db.Column(db.String, db.ForeignKey('batch.batch_id'))
    batch = db.relationship('Batch', backref = db.backref('sample'))
    sample_ID = db.Column(db.String, unique = False)
    Flowcell = db.Column(db.String, unique = False)
    Description = db.Column(db.String, unique = False)
    IndexID = db.Column(db.String, unique = False)
    Index = db.Column(db.String, unique = False)
    Well = db.Column(db.String, unique = False)
    Library_nM = db.Column(db.String, unique = False)
    QCFlag = db.Column(db.String, unique = False)
    QCFailure = db.Column(db.String, unique = False)
    QCWarning = db.Column(db.String, unique = False)
    Clusters = db.Column(db.String, unique = False)
    TotalReads2Clusters = db.Column(db.String, unique = False)
    MaxMisindexedReads2Clusters = db.Column(db.String, unique = False)
    IndexedReads = db.Column(db.String, unique = False)
    TotalIndexedReads2Clusters = db.Column(db.String, unique = False)
    Tags = db.Column(db.String, unique = False)
    NonExcludedSites = db.Column(db.String, unique = False)
    NonExcludedSites2Tags = db.Column(db.String, unique = False)
    Tags2IndexedReads = db.Column(db.String, unique = False)
    PerfectMatchTags2Tags = db.Column(db.String, unique = False)
    GCBias = db.Column(db.String, unique = False)
    GCR2 = db.Column(db.String, unique = False)
    status_T13 = db.Column(db.String, unique = False)
    status_T18 = db.Column(db.String, unique = False)
    status_T21 = db.Column(db.String, unique = False)
    status_X0 = db.Column(db.String, unique = False)
    status_XXX = db.Column(db.String, unique = False)
    status_XXY = db.Column(db.String, unique = False)
    status_XYY = db.Column(db.String, unique = False)
    status_change_T13 = db.Column(db.String, unique = False)                           
    status_change_T18 = db.Column(db.String, unique = False)                           
    status_change_T21 = db.Column(db.String, unique = False)                           
    status_change_X0 = db.Column(db.String, unique = False)                            
    status_change_XXX = db.Column(db.String, unique = False)                           
    status_change_XXY = db.Column(db.String, unique = False)                           
    status_change_XYY = db.Column(db.String, unique = False) 
    comment_T13 = db.Column(db.String, unique = False)
    comment_T18 = db.Column(db.String, unique = False)
    comment_T21 = db.Column(db.String, unique = False)
    comment_X0 = db.Column(db.String, unique = False)
    comment_XXX = db.Column(db.String, unique = False)
    comment_XXY = db.Column(db.String, unique = False)
    comment_XYY = db.Column(db.String, unique = False)


    def __init__(self, nipt_dict, batch):
        self.batch = batch
        self.sample_ID = nipt_dict['SampleID']
        self.Flowcell = nipt_dict['Flowcell']
        self.Description = nipt_dict['Description']
        self.SampleProject = nipt_dict['SampleProject']
        self.IndexID = nipt_dict['IndexID']
        self.Index = nipt_dict['Index']
        self.Well = nipt_dict['Well']
        self.Library_nM = nipt_dict['Library_nM']
        self.QCFlag = nipt_dict['QCFlag']
        self.QCFailure = nipt_dict['QCFailure']
        self.QCWarning = nipt_dict['QCWarning']
        self.Clusters = nipt_dict['Clusters']
        self.TotalReads2Clusters = nipt_dict['TotalReads2Clusters']
        self.MaxMisindexedReads2Clusters = nipt_dict['MaxMisindexedReads2Clusters']
        self.IndexedReads = nipt_dict['IndexedReads']
        self.TotalIndexedReads2Clusters = nipt_dict['TotalIndexedReads2Clusters']
        self.Tags = nipt_dict['Tags']
        self.NonExcludedSites = nipt_dict['NonExcludedSites']
        self.NonExcludedSites2Tags = nipt_dict['NonExcludedSites2Tags']
        self.Tags2IndexedReads = nipt_dict['Tags2IndexedReads']
        self.PerfectMatchTags2Tags = nipt_dict['PerfectMatchTags2Tags']
        self.GCBias = nipt_dict['GCBias']
        self.GCR2 = nipt_dict['GCR2']
        self.status_T13 = 'Normal'
        self.status_T18 = 'Normal'
        self.status_T21 = 'Normal'
        self.status_X0 = 'Normal'
        self.status_XX = 'Normal'
        self.status_XXY = 'Normal'
        self.status_XYY = 'Normal'
        self.status_XXX = 'Normal'
        self.status_change_T13 = ''
        self.status_change_T18 = ''
        self.status_change_T21 = ''
        self.status_change_X0 = ''
        self.status_change_XX = ''
        self.status_change_XXY = ''
        self.status_change_XYY = ''
        self.status_change_XXX = ''
        self.comment_T13 = ''
        self.comment_T18 = ''
        self.comment_T21 = ''
        self.comment_XXX = ''
        self.comment_XXY = ''
        self.comment_XYY = ''
        self.comment_X0 = ''

    def __repr__(self):
        return '<User %r>' % self.sample_ID


class Coverage(db.Model):
    __table_name__ = 'Coverage'
    id = db.Column(db.Integer, primary_key = True)
    sample_ID = db.Column(db.String, db.ForeignKey('sample.sample_ID'))
    sample = db.relationship('Sample', backref = db.backref('Coverage'))
    batch_id = db.Column(db.String, db.ForeignKey('batch.batch_id'))
    batch = db.relationship('Batch', backref = db.backref('Coverage'))
    Chr1_Coverage = db.Column(db.String, unique = False)
    Chr2_Coverage = db.Column(db.String, unique = False)
    Chr3_Coverage = db.Column(db.String, unique = False)
    Chr4_Coverage = db.Column(db.String, unique = False)
    Chr5_Coverage = db.Column(db.String, unique = False)
    Chr6_Coverage = db.Column(db.String, unique = False)
    Chr7_Coverage = db.Column(db.String, unique = False)
    Chr8_Coverage = db.Column(db.String, unique = False)
    Chr9_Coverage = db.Column(db.String, unique = False)
    Chr10_Coverage = db.Column(db.String, unique = False)
    Chr11_Coverage = db.Column(db.String, unique = False)
    Chr12_Coverage = db.Column(db.String, unique = False)
    Chr13_Coverage = db.Column(db.String, unique = False)
    Chr14_Coverage = db.Column(db.String, unique = False)
    Chr15_Coverage = db.Column(db.String, unique = False)
    Chr16_Coverage = db.Column(db.String, unique = False)
    Chr17_Coverage = db.Column(db.String, unique = False)
    Chr18_Coverage = db.Column(db.String, unique = False)
    Chr19_Coverage = db.Column(db.String, unique = False)
    Chr20_Coverage = db.Column(db.String, unique = False)
    Chr21_Coverage = db.Column(db.String, unique = False)
    Chr22_Coverage = db.Column(db.String, unique = False)
    ChrX_Coverage = db.Column(db.String, unique = False)
    ChrY_Coverage = db.Column(db.String, unique = False)
    Chr1 = db.Column(db.String, unique = False)
    Chr2 = db.Column(db.String, unique = False)
    Chr3 = db.Column(db.String, unique = False)
    Chr4 = db.Column(db.String, unique = False)
    Chr5 = db.Column(db.String, unique = False)
    Chr6 = db.Column(db.String, unique = False)
    Chr7 = db.Column(db.String, unique = False)
    Chr8 = db.Column(db.String, unique = False)
    Chr9 = db.Column(db.String, unique = False)
    Chr10 = db.Column(db.String, unique = False)
    Chr11 = db.Column(db.String, unique = False)
    Chr12 = db.Column(db.String, unique = False)
    Chr13 = db.Column(db.String, unique = False)
    Chr14 = db.Column(db.String, unique = False)
    Chr15 = db.Column(db.String, unique = False)
    Chr16 = db.Column(db.String, unique = False)
    Chr17 = db.Column(db.String, unique = False)
    Chr18 = db.Column(db.String, unique = False)
    Chr19 = db.Column(db.String, unique = False)
    Chr20 = db.Column(db.String, unique = False)
    Chr21 = db.Column(db.String, unique = False)
    Chr22 = db.Column(db.String, unique = False)
    ChrX = db.Column(db.String, unique = False)
    ChrY = db.Column(db.String, unique = False)



    def __init__(self, nipt_dict, sample, batch):
        self.sample = sample
        self.batch = batch
        self.Chr1_Coverage = nipt_dict["Chr1_Coverage"]
        self.Chr2_Coverage = nipt_dict["Chr2_Coverage"]
        self.Chr3_Coverage = nipt_dict["Chr3_Coverage"]
        self.Chr4_Coverage = nipt_dict["Chr4_Coverage"]
        self.Chr5_Coverage = nipt_dict["Chr5_Coverage"]
        self.Chr6_Coverage = nipt_dict["Chr6_Coverage"]
        self.Chr7_Coverage = nipt_dict["Chr7_Coverage"]
        self.Chr8_Coverage = nipt_dict["Chr8_Coverage"]
        self.Chr9_Coverage = nipt_dict["Chr9_Coverage"]
        self.Chr10_Coverage = nipt_dict["Chr10_Coverage"]
        self.Chr11_Coverage = nipt_dict["Chr11_Coverage"]
        self.Chr12_Coverage = nipt_dict["Chr12_Coverage"]
        self.Chr13_Coverage = nipt_dict["Chr13_Coverage"]
        self.Chr14_Coverage = nipt_dict["Chr14_Coverage"]
        self.Chr15_Coverage = nipt_dict["Chr15_Coverage"]
        self.Chr16_Coverage = nipt_dict["Chr16_Coverage"]
        self.Chr17_Coverage = nipt_dict["Chr17_Coverage"]
        self.Chr18_Coverage = nipt_dict["Chr18_Coverage"]
        self.Chr19_Coverage = nipt_dict["Chr19_Coverage"]
        self.Chr20_Coverage = nipt_dict["Chr20_Coverage"]
        self.Chr21_Coverage = nipt_dict["Chr21_Coverage"]
        self.Chr22_Coverage = nipt_dict["Chr22_Coverage"]
        self.ChrX_Coverage = nipt_dict["ChrX_Coverage"]
        self.ChrY_Coverage = nipt_dict["ChrY_Coverage"]
        self.Chr1 = nipt_dict["Chr1"]
        self.Chr2 = nipt_dict["Chr2"]
        self.Chr3 = nipt_dict["Chr3"]
        self.Chr4 = nipt_dict["Chr4"]
        self.Chr5 = nipt_dict["Chr5"]
        self.Chr6 = nipt_dict["Chr6"]
        self.Chr7 = nipt_dict["Chr7"]
        self.Chr8 = nipt_dict["Chr8"]
        self.Chr9 = nipt_dict["Chr9"]
        self.Chr10 = nipt_dict["Chr10"]
        self.Chr11 = nipt_dict["Chr11"]
        self.Chr12 = nipt_dict["Chr12"]
        self.Chr13 = nipt_dict["Chr13"]
        self.Chr14 = nipt_dict["Chr14"]
        self.Chr15 = nipt_dict["Chr15"]
        self.Chr16 = nipt_dict["Chr16"]
        self.Chr17 = nipt_dict["Chr17"]
        self.Chr18 = nipt_dict["Chr18"]
        self.Chr19 = nipt_dict["Chr19"]
        self.Chr20 = nipt_dict["Chr20"]
        self.Chr21 = nipt_dict["Chr21"]
        self.Chr22 = nipt_dict["Chr22"]
        self.ChrX = nipt_dict["ChrX"]
        self.ChrY = nipt_dict["ChrY"]

    def __repr__(self):
        return '<User %r>' % self.sample_ID


class NCV(db.Model):
    __table_name__ = 'NCV'
    id = db.Column(db.Integer, primary_key = True)
    sample_ID = db.Column(db.String, db.ForeignKey('sample.sample_ID'))
    sample = db.relationship('Sample', backref = db.backref('NCV'))
    batch_id = db.Column(db.String, db.ForeignKey('batch.batch_id'))
    batch = db.relationship('Batch', backref = db.backref('NCV'))
    SampleType  = db.Column(db.String, unique = False)
    NCV_13 = db.Column(db.String, unique = False)
    NCV_18 = db.Column(db.String, unique = False)
    NCV_21 = db.Column(db.String, unique = False)
    NCV_X = db.Column(db.String, unique = False)
    NCV_Y = db.Column(db.String, unique = False)
    Ratio_13 = db.Column(db.String, unique = False)
    Ratio_18 = db.Column(db.String, unique = False)
    Ratio_21 = db.Column(db.String, unique = False)
    Ratio_X = db.Column(db.String, unique = False)
    Ratio_Y = db.Column(db.String, unique = False)
    NCD_13 = db.Column(db.String, unique = False)
    NCD_18 = db.Column(db.String, unique = False)
    NCD_21 = db.Column(db.String, unique = False)
    NCD_X = db.Column(db.String, unique = False)
    NCD_Y = db.Column(db.String, unique = False)
    include = db.Column(db.Boolean, unique = False)
    change_include_date = db.Column(db.String, unique = False)

    def __init__(self, nipt_dict, sample, batch): 
        self.sample = sample
        self.batch = batch
        self.SampleType = nipt_dict['SampleType']
        self.NCV_13 = nipt_dict['NCV_13']
        self.NCV_18 = nipt_dict['NCV_18']
        self.NCV_21 = nipt_dict['NCV_21']
        self.NCV_X = nipt_dict['NCV_X']
        self.NCV_Y = nipt_dict['NCV_Y']     
        self.Ratio_13 = nipt_dict['Ratio_13']
        self.Ratio_18 = nipt_dict['Ratio_18']
        self.Ratio_21 = nipt_dict['Ratio_21']
        self.Ratio_X = nipt_dict['Ratio_X']
        self.Ratio_Y = nipt_dict['Ratio_Y']
        self.NCD_13 = nipt_dict['NCD_13']
        self.NCD_18 = nipt_dict['NCD_18']
        self.NCD_21 = nipt_dict['NCD_21']
        self.NCD_X = nipt_dict['NCD_X']
        self.NCD_Y = nipt_dict['NCD_Y']
        self.include = True             # set to False by default before handing over!!!
        self.change_include_date = ''

    def __repr__(self):
        return '<User %r>' % self.sample_ID


class BatchStat(db.Model):
    __table_name__ = 'BatchStat'
    id = db.Column(db.Integer, primary_key = True)
    batch_id = db.Column(db.String, db.ForeignKey('batch.batch_id'))
    batch = db.relationship('Batch', backref = db.backref('BatchStat'))
    Median_13 = db.Column(db.String, unique = False)
    Median_18 = db.Column(db.String, unique = False)
    Median_21 = db.Column(db.String, unique = False)
    Median_X = db.Column(db.String, unique = False)
    Median_Y = db.Column(db.String, unique = False)
    Stdev_13 = db.Column(db.String, unique = False)
    Stdev_18 = db.Column(db.String, unique = False)
    Stdev_21 = db.Column(db.String, unique = False)
    Stdev_X = db.Column(db.String, unique = False)
    Stdev_Y = db.Column(db.String, unique = False)

    
    def __init__(self, nipt_dict, batch):  
        self.batch = batch
        self.Median_13 = nipt_dict['Median_13']
        self.Median_18 = nipt_dict['Median_18']
        self.Median_21 = nipt_dict['Median_21']
        self.Median_X = nipt_dict['Median_X']
        self.Median_Y = nipt_dict['Median_Y']
        self.Stdev_13 = nipt_dict['Stdev_13']
        self.Stdev_18 = nipt_dict['Stdev_18']
        self.Stdev_21 = nipt_dict['Stdev_21']
        self.Stdev_X = nipt_dict['Stdev_X']
        self.Stdev_Y = nipt_dict['Stdev_Y']
    
    def __repr__(self):
        return '<User %r>' % self.batch_id



class Batch(db.Model):
    __table_name__ = 'batch'
    id = db.Column(db.Integer, primary_key = True)
    batch_id = db.Column(db.String(80), unique = False)
    date = db.Column(db.String(80), unique = False)
    flowcell = db.Column(db.String(15), unique = False)
    batch_name = db.Column(db.String(15), unique = False)

    def __init__(self, batch_id, date, flowcell):
        self.batch_id = batch_id 
        self.batch_name = None
        self.date = date
        self.flowcell = flowcell

    def __repr__(self):
        return '<User %r>' % self.batch_id


class NiptDBSetup():

    def __init__(self, csv_file_path):
        self.nipt_results = self.parse_path(csv_file_path+'/*NIPT_RESULTS.csv')
        self.sample_sheet = self.parse_path(csv_file_path+'/SampleSheet.csv')
        f_name_info = csv_file_path.split('/')[-1].split('_')
        self.batch_id = f_name_info[2]
        self.date = f_name_info[0]
        self.flowcell = f_name_info[3]
        

    def update_nipt_db(self):
        reader = csv.DictReader(open(self.nipt_results, 'rb'))
        batch = Batch.query.filter_by(batch_id = self.batch_id).first()    
        if not batch:
            batch = Batch(self.batch_id, self.date, self.flowcell)
            db.session.add(batch)
        for row in reader:
            if not Sample.query.filter_by(sample_ID = row['SampleID']).first():
                sample = Sample(row, batch)
                db.session.add(sample)
                cov = Coverage(row, sample, batch)
                db.session.add(cov)
                ncv = NCV(row, sample, batch)
                db.session.add(ncv)
            if not BatchStat.query.filter_by(batch_id = self.batch_id).first():
                batchstat = BatchStat(row, batch)
                db.session.add(batchstat)
        try:
            db.session.commit()
        except: 
            error = sys.exc_info()
            logging.error('error in update_nipt_db!!!!!!!')
            logging.error(error)
            pass


    def set_batch_id_from_sample_sheet(self):
        sheet = open(self.sample_sheet, 'rb')
        for l in sheet:
            if 'Investigator Name' in l:
                try:
                    investigator_name = l.split(',')[1].split('_')
                    batch_name = investigator_name[1]
                    batch = Batch.query.filter_by(batch_id = self.batch_id).first()
                    batch.batch_name = batch_name
                    db.session.add(batch)
                    db.session.commit()
                except:
                    pass

    def parse_path(self, path):
        if glob.glob(path):
            return glob.glob(path)[0]
        else:
            return None


def main(csv_files):
    logging.basicConfig(filename = 'NIPT_log', level=logging.INFO)
    db.create_all()
    for path in csv_files:
        path = path.rstrip('/')
        NDBS = NiptDBSetup(path)
        if NDBS.nipt_results:
            NDBS.update_nipt_db()
        if NDBS.sample_sheet:
            NDBS.set_batch_id_from_sample_sheet()
    
if __name__ == '__main__':
    parser = ArgumentParser(description= 'bla bla')
    parser.add_argument('--csv_files',nargs='+', 
            default = None , 
            dest = 'csv', help = 'list of pathes to NIPT csv resultfiles')

    args = parser.parse_args()
    main(args.csv)



