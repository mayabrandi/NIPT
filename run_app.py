# encoding: utf-8
from flask import redirect, render_template, request
from nipt_db import Sample, Batch, Coverage, NCV, BatchStat,  app, db
import numpy as np
import logging
from datetime import datetime



class BatchDataHandler():
    def __init__(self, batch_id):
        self.batch_id = batch_id
        self.filtered_NCV = self.fliter_NA()
        self.NCV_passed = self.filtered_NCV.filter(NCV.include)
        self.cases = self.filtered_NCV.filter(NCV.batch_id == batch_id,
                                            NCV.sample_ID.notilike('%ref%'),
                                            NCV.sample_ID.notilike('%Control%'))
        self.samples_on_batch = Sample.query.filter(Sample.batch_id == batch_id)
        self.NCV_on_batch = NCV.query.filter(NCV.batch_id == batch_id)
        self.nr_samples_on_batch = len(self.NCV_on_batch.all())
        self.NCV_names = ['NCV_13','NCV_18','NCV_21','NCV_X','NCV_Y']
        self.NCV_data = {}
        self.NCV_warnings = {}
        self.warnings = {}    

    def fliter_NA(self):
        # Filtering out NA. Could probably be done in a more preyyt way :/
        return NCV.query.filter(
                NCV.NCV_13!='NA',
                NCV.NCV_18!='NA',
                NCV.NCV_21!='NA',
                NCV.NCV_X!='NA',
                 NCV.NCV_Y!='NA')

    def handle_NCV(self):
        for s in self.NCV_on_batch:
            samp_warn = []
            self.NCV_data[s.sample_ID] = {}
            for key in self.NCV_names:
                if s.__dict__[key] == 'NA':
                    warn = False
                    val = 'NA'
                elif  key in ['NCV_13','NCV_18','NCV_21'] and float(s.__dict__[key]) > 3:
                    samp_warn.append(key)
                    warn = True
                    val = round(float(s.__dict__[key]),2)
                else:
                    warn = False
                    val = round(float(s.__dict__[key]),2)
                self.NCV_data[s.sample_ID][key] = {'val': val, 'warn': warn }
            if samp_warn:
                self.NCV_warnings[s.sample_ID] = ', '.join(samp_warn)

    def get_warnings(self):
#        low_NES = self.samples_on_batch.filter(Sample.NonExcludedSites < 8000000)
        QC_flagged = self.samples_on_batch.filter(Sample.QCFlag > 0)
#        for sample in set(self.NCV_warnings.keys() + [sample.sample_ID for sample in low_NES] + [sample.sample_ID for sample in QC_flagged]):
#            self.warnings[sample] = {'sample_ID' : sample, 'missing_data' : '', 'QC_warn' : '', 'QC_fail' : '', 'NCV_low': ''}
        for sample in set(self.NCV_warnings.keys() + [sample.sample_ID for sample in QC_flagged]):
            self.warnings[sample] = {'sample_ID' : sample, 'QC_warn' : '', 'QC_fail' : ''}
        for sample_id, warning in self.NCV_warnings.items():
            self.warnings[sample_id]['NCV_high'] = warning
#        for sample in low_NES:
#            self.warnings[sample.sample_ID]['missing_data'] = 'warning: lt 8M reads'
        for sample in QC_flagged:
            self.warnings[sample.sample_ID]['QC_fail'] = sample.QCFailure if sample.QCFailure else ''
            self.warnings[sample.sample_ID]['QC_warn'] = sample.QCWarning if sample.QCWarning else ''
    

class PlottPage():
    """Class to preppare data for NCV plots"""
    def __init__(self, batch_id):
        self.BDH = BatchDataHandler(batch_id)
        self.NCV_passed = self.BDH.NCV_passed 
        self.cases = self.BDH.cases  
        self.NCV_stat = {'NCV_13':{}, 'NCV_18':{}, 
                         'NCV_21':{}, 'NCV_X':{}, 'NCV_Y' : {}}
        self.tris_chrom_abn = {'13':{},
                               '18':{},
                               '21':{}}
        self.sex_chrom_abn = {'X0':{},
                              'XXX':{},
                              'XXY':{},
                              'XYY':{}}
        self.X_labels = self.make_X_labels()
        self.sample_state_dict = {'Probable':{},'False Positive':{},'Verified':{}, "False Negative": {}, "Other": {}, "Suspected": {}}
    
    def make_approved_stats(self, chrom):
        NCV_pass = []
        for s in self.NCV_passed:
            try: 
                NCV_pass.append(float(s.__dict__[chrom])) 
            except:
                pass
        return [list( NCV_pass)]

    def make_X_labels(self):
        X_labels = [s.__dict__['sample_ID'] for s in self.cases]
        return X_labels

    def make_NCV_stat(self):
        for chrom in self.NCV_stat.keys():
            NCV_pass = self.make_approved_stats(chrom)
            NCV_list = [[s.__dict__['sample_ID'], 
                    round(float(s.__dict__[chrom]),2)] for s in self.cases]
            NCV_cases = [round(float(s.__dict__[chrom]),2) for s in self.cases]
            X_labels = [s.__dict__['sample_ID'] for s in self.cases]
            self.NCV_stat[chrom] = {
                'nr_pass':len(NCV_pass[0]),
                'NCV_list' : NCV_list,
                'NCV_cases' : NCV_cases,
                'x_axis' : range(2,len(NCV_cases)+2),
                'X_labels' : X_labels,
                'chrom' : chrom,
                'NCV_pass' : NCV_pass}

    def make_chrom_abn(self):
        x = 0.6
        for abn in ['13','18','21']:
            for status in self.sample_state_dict.keys():                                       
                self.tris_chrom_abn[abn][status] = {'NCV' : [], 's_name' : [], 'x_axis': []}             
                for s in Sample.query.filter(Sample.__dict__['status_T'+abn] == status):
                    NCV_val = NCV.query.filter_by(sample_ID = s.sample_ID).first().__dict__['NCV_' + abn]
                    self.tris_chrom_abn[abn][status]['NCV'].append(float(NCV_val))
                    self.tris_chrom_abn[abn][status]['s_name'].append(s.sample_ID)
                    self.tris_chrom_abn[abn][status]['x_axis'].append(x)
            x = x+1

class SamplePage():
    def __init__(self, batch_id):
        self.BDH = BatchDataHandler(batch_id)


###---------------- ROUTS ------------------###


@app.route('/login/')
def login():
    return render_template('login.html')

@app.route('/NIPT/')
def batch():
    return render_template('start_page.html', 
        batches = Batch.query,
        samples = Sample.query)

@app.route('/update', methods=['POST'])
def update():
    dt = datetime.now()
    if 'All samples' in request.form:
        samples = request.form['All samples'].split(',')
        for sample_id in samples:
            sample = NCV.query.filter_by(sample_ID = sample_id).first()
            if not sample.include:
                sample.change_include_date = dt.strftime('%Y/%m/%d %H:%M:%S')
            sample.include = True
            db.session.add(sample)
    elif 'sample_ids' in request.form:
        all_samples = request.form['sample_ids'].split(',')
        for sample_id in all_samples:
            sample = NCV.query.filter_by(sample_ID = sample_id).first()
            if sample_id in request.form:
                if not sample.include:
                    sample.change_include_date = dt.strftime('%Y/%m/%d %H:%M:%S')
                sample.include = True
            else:
                if sample.include:
                    sample.change_include_date = dt.strftime('%Y/%m/%d %H:%M:%S')
                sample.include = False
    db.session.commit()
    return redirect(request.referrer)

@app.route('/NIPT/<batch_id>/<sample_id>/update_trisomi_status', methods=['POST'])
def update_trisomi_status(batch_id, sample_id):
    dt = datetime.now()  
    sample = Sample.query.filter_by(sample_ID = sample_id).first()

## Wont work.... 
#    chr_abn = ['T13','T18', 'T21', 'X0', 'XXX','XXY','XYY']     
#    for abn in chr_abn:
        #sample.__dict__["comment_"+abn] = request.form["comment_"+abn]
#        sample.__dict__["status_"+abn] = request.form[abn]
#        sample.__dict__["status_change_"+abn] = dt.strftime('%Y/%m/%d %H:%M:%S')

    if sample.status_T13 != request.form['T13']:
        sample.status_T13 = request.form['T13']
        sample.status_change_T13 = dt.strftime('%Y/%m/%d %H:%M:%S')
    if sample.comment_T13 != request.form["comment_T13"]:
        sample.comment_T13 = request.form["comment_T13"]
        sample.status_change_T13 = dt.strftime('%Y/%m/%d %H:%M:%S')

    if sample.status_T18 != request.form['T18']:
        sample.status_T18 = request.form['T18']
        sample.status_change_T18 = dt.strftime('%Y/%m/%d %H:%M:%S')
    if sample.comment_T18 != request.form["comment_T18"]:
        sample.comment_T18 = request.form["comment_T18"]
        sample.status_change_T18 = dt.strftime('%Y/%m/%d %H:%M:%S')

    if sample.status_T21 != request.form['T21']:
        sample.status_T21 = request.form['T21']
        sample.status_change_T21 = dt.strftime('%Y/%m/%d %H:%M:%S')
    if sample.comment_T21 != request.form["comment_T21"]:
        sample.comment_T21 = request.form["comment_T21"]
        sample.status_change_T21 = dt.strftime('%Y/%m/%d %H:%M:%S')

    if sample.status_X0 != request.form['X0']:
        sample.status_change_X0 = dt.strftime('%Y/%m/%d %H:%M:%S')
        sample.status_X0 = request.form['X0']
    if sample.comment_X0 != request.form["comment_X0"]:
        sample.comment_X0 = request.form["comment_X0"]
        sample.status_change_X0 = dt.strftime('%Y/%m/%d %H:%M:%S')

    if sample.status_XXX != request.form['XXX']:
        sample.status_change_XXX = dt.strftime('%Y/%m/%d %H:%M:%S')
        sample.status_XXX = request.form['XXX']
    if sample.comment_XXX != request.form["comment_XXX"]:
        sample.comment_XXX = request.form["comment_XXX"]
        sample.status_change_XXX = dt.strftime('%Y/%m/%d %H:%M:%S')

    if sample.status_XXY != request.form['XXY']:
        sample.status_change_XXY = dt.strftime('%Y/%m/%d %H:%M:%S')
        sample.status_XXY = request.form['XXY']
    if sample.comment_XXY != request.form["comment_XXY"]:
        sample.comment_XXY = request.form["comment_XXY"]
        sample.status_change_XXY = dt.strftime('%Y/%m/%d %H:%M:%S')

    if sample.status_XYY != request.form['XYY']:
        sample.status_change_XYY = dt.strftime('%Y/%m/%d %H:%M:%S')
        sample.status_XYY = request.form['XYY']
    if sample.comment_XYY != request.form["comment_XYY"]:
        sample.comment_XYY = request.form["comment_XYY"]
        sample.status_change_XYY = dt.strftime('%Y/%m/%d %H:%M:%S')

    db.session.add(sample)
    db.session.commit()
    return redirect(request.referrer)

@app.route('/NIPT/<batch_id>/')
def sample(batch_id):
    BDH = BatchDataHandler(batch_id)
    BDH.handle_NCV()
    BDH.get_warnings()
    return render_template('batch_page.html', 
            samples = BDH.NCV_on_batch,
            warnings = BDH.warnings, 
            NCV_rounded = BDH.NCV_data,
            batch_id = batch_id,
            sample_ids = ','.join(sample.sample_ID for sample in BDH.NCV_on_batch))

@app.route('/NIPT/<batch_id>/<sample_id>/')
def sample_page(batch_id, sample_id):
    sample = Sample.query.filter_by(sample_ID = sample_id).first()
    NCV_dat = NCV.query.filter_by(sample_ID = sample_id).first()
    chrom_abnorm = ['T13','T18', 'T21', 'X0', 'XXX','XXY','XYY']
    db_entries = {c:sample.__dict__['status_'+c].replace('\r\n', '').strip() for c in chrom_abnorm }
    db_entries_change = {c:sample.__dict__['status_change_'+c]  for c in chrom_abnorm}              
    db_entries_comments = {c : sample.__dict__['comment_'+c]  for c in chrom_abnorm}
    PP = PlottPage(batch_id)
    PP.make_NCV_stat()
    PP.make_chrom_abn()
    sample_state_dict = PP.sample_state_dict
    print db_entries_comments
    print sample.comment_T13
    for state in sample_state_dict:
        sample_state_dict[state]['T_13'] = Sample.query.filter_by(status_T13 = state)
        sample_state_dict[state]['T_18'] = Sample.query.filter_by(status_T18 = state)
        sample_state_dict[state]['T_21'] = Sample.query.filter_by(status_T21 = state)

    return render_template('sample_page.html',
            NCV_dat = NCV_dat,
            chrom_abn = PP.tris_chrom_abn,
            sample = sample, 
            batch_id = batch_id,
            sample_id = sample_id,
            chrom_abnorm = chrom_abnorm,
            db_entries = db_entries,
            db_entries_comments = db_entries_comments,
            db_entries_change = db_entries_change,
            NCV_stat = PP.NCV_stat,
            NCV_131821 = ['NCV_13', 'NCV_18', 'NCV_21'],
            state_dict = sample_state_dict)

@app.route('/NIPT/<batch_id>/NCV_plots/')
def NCV_plots(batch_id):
    PP = PlottPage(batch_id)
    PP.make_NCV_stat()
    state_dict = {'Probable':{},'False Positive':{},'Verified':{}}
    for state in state_dict:
        state_dict[state]['T_13'] = Sample.query.filter_by(status_T13 = state)
        state_dict[state]['T_18'] = Sample.query.filter_by(status_T18 = state)
        state_dict[state]['T_21'] = Sample.query.filter_by(status_T21 = state)
    return render_template('NCV_plots.html',
        samples = PP.BDH.samples_on_batch,
        batch_id = batch_id,
        NCV_stat = PP.NCV_stat,
        NCV_131821 = ['NCV_13', 'NCV_18', 'NCV_21'],
        samp_range = range(len(PP.NCV_stat['NCV_X']['NCV_cases'])),
        state_dict = state_dict)

def main():
    logging.basicConfig(filename = 'NIPT_log', level=logging.INFO)
    app.run(debug=True)    

if __name__ == "__main__":
    main()


