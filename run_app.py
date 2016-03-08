# encoding: utf-8
from flask import flash, abort, url_for, redirect, render_template, request, session
from flask_login import login_user,logout_user, current_user, login_required
from flask.ext.mail import Message
from flask_oauthlib.client import OAuthException
from database import User, Sample, Batch, Coverage, NCV, BatchStat, db
from extentions import login_manager, google, app, mail, ssl, ctx
import numpy as np
import logging
import os
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

    def fliter_NA(self):
        # Filtering out NA. Could probably be done in a more preyyt way :/
        return NCV.query.filter(
                NCV.NCV_13!='NA',
                NCV.NCV_18!='NA',
                NCV.NCV_21!='NA',
                NCV.NCV_X!='NA',
                NCV.NCV_Y!='NA')


class DataClasifyer():
    def __init__(self):
        self.NCV_data = {} 
        self.NCV_names = ['13','18','21','X','Y']
        self.NCV_warnings = {}
        self.warnings = {}
        self.sex_tresholds = {'XY_horis' :  {'x' : [-30, 10],   'y' : [13, 13]},
                                'XY_upper': {'x' : [-30, 5.05], 'y' : [553.687, 13.6016]},
                                'XY_lower': {'x' : [-30, -5,13],'y' : [395.371, 13.971]},
                                'XXY' :     {'x' : [-4, -4],    'y' : [155, 350]},
                                'X0' :      {'x' : [-4, -4],   'y' : [13, -30]},
                                'XXX' :     {'x' : [4, 4],      'y' : [13, -30]}}
        self.tris_thresholds = {'soft_max': {'NCV': 3 , 'color': 'orange'},
                                'soft_min': {'NCV': -4, 'color': 'orange'},
                                'hard_max': {'NCV': 4 , 'color': 'red'},
                                'hard_min': {'NCV': -5, 'color': 'red'} }

    def handle_NCV(self, NCV_db):
        for s in NCV_db:
            samp_warn = []
            sex_warn = []
            self.NCV_data[s.sample_ID] = {}
            exceptions = ['NA','']
            for key in self.NCV_names:
                if s.__dict__['NCV_'+key] in exceptions:
                    val = s.__dict__['NCV_'+key]
                    warn = "default"
                else:
                    val = round(float(s.__dict__['NCV_'+key]),2)
                    if  key in ['13','18','21']:
                        hmin = self.tris_thresholds['hard_min']['NCV']
                        hmax = self.tris_thresholds['hard_max']['NCV']
                        smin = self.tris_thresholds['soft_min']['NCV']
                        smax = self.tris_thresholds['soft_max']['NCV']
                        if (smax <= val < hmax) or (hmin < val <= smin):
                            warn = "warning"
                            samp_warn.append('T'+key)
                        elif (val >= hmax) or (val <= hmin):
                            warn = "danger"
                            samp_warn.append('T'+key)
                        else:
                            warn = "default"
                self.NCV_data[s.sample_ID]['NCV_'+key] = {'val': val, 'warn': warn }
            if not set([s.NCV_X , s.NCV_Y]).issubset(exceptions):
                x = float(s.NCV_X)
                y = float(s.NCV_Y)
                f_h = -15.409*x + 91.417 - y
                f_l = -15.256*x - 62.309 - y
                if 0>=f_h and x<=-4:
                    sex_warn = 'XYY'
                    
                elif 0>=f_h and x>=-4 and y>13:
                    sex_warn = 'XXY'
                elif y<13 and x>=4:
                    sex_warn = 'XXX'
              ##  elif f_l<0<=f_h and y>13:
                ##    sex_warn = 'XY'
                elif f_l>0 and x< -4:
                    sex_warn = 'X0'
              #  elif -4>=x>=4 and y<13:
              #      sex_warn = 'XX'
            if sex_warn:
                self.NCV_data[s.sample_ID]['NCV_Y']['warn'] = "danger"
                self.NCV_data[s.sample_ID]['NCV_X']['warn'] = "danger"
                samp_warn.append(sex_warn)
            else:
                self.NCV_data[s.sample_ID]['NCV_Y']['warn'] = "default"
                self.NCV_data[s.sample_ID]['NCV_X']['warn'] = "default"
            self.NCV_warnings[s.sample_ID] = ', '.join(samp_warn)

    def get_warnings(self, samples):
#        low_NES = self.BDH.samples_on_batch.filter(Sample.NonExcludedSites < 8000000)
        QC_flagged = samples.filter(Sample.QCFlag > 0)
        ##QC_flagged = self.BDH.samples_on_batch.filter(Sample.QCFlag > 0)
#        for sample in set(self.NCV_warnings.keys() + [sample.sample_ID for sample in low_NES] + [sample.sample_ID for sample in QC_flagged]):
#            self.warnings[sample] = {'sample_ID' : sample, 'missing_data' : '', 'QC_warn' : '', 'QC_fail' : '', 'NCV_low': ''}
#        for sample in set(self.NCV_warnings.keys() + [sample.sample_ID for sample in QC_flagged]):
        for sample in set([sample.sample_ID for sample in QC_flagged]):
            self.warnings[sample] = {'sample_ID' : sample, 'QC_warn' : '', 'QC_fail' : ''}
       # for sample_id, warning in self.NCV_warnings.items():
         #   self.warnings[sample_id]['NCV_high'] = warning
#        for sample in low_NES:
#            self.warnings[sample.sample_ID]['missing_data'] = 'warning: lt 8M reads'
        for sample in QC_flagged:
            self.warnings[sample.sample_ID]['QC_fail'] = sample.QCFailure if sample.QCFailure else ''
            self.warnings[sample.sample_ID]['QC_warn'] = sample.QCWarning if sample.QCWarning else ''



class PlottPage():
    """Class to preppare data for NCV plots"""
    def __init__(self, batch_id):
        self.batch_id = batch_id
        self.BDH = BatchDataHandler(batch_id)
        self.NCV_passed = self.BDH.NCV_passed
        self.nr_validation_samps = len(self.BDH.NCV_passed.all()) 
        self.cases = self.BDH.cases  
        self.NCV_stat = {'NCV_13':{}, 'NCV_18':{}, 
                         'NCV_21':{}, 'NCV_X':{}, 'NCV_Y' : {}}
        self.coverage_plot = {'samples':{},'x_axis':[]}
        self.tris_chrom_abn = {'13':{},
                               '18':{},
                               '21':{}}
        self.tris_abn = {}
        self.sex_chrom_abn = {'X0':{},
                              'XXX':{},
                              'XXY':{},
                              'XYY':{}}
        self.X_labels = self.make_X_labels()
        self.sample_state_dict = {'Probable' : {},'False Positive':{},'Verified':{}, "False Negative": {}, "Other": {}, "Suspected": {}}

    def make_approved_stats(self, chrom):
        NCV_pass = []
        NCV_pass_names = []
        for s in self.NCV_passed:
            try: 
                NCV_pass.append(float(s.__dict__[chrom])) 
                NCV_pass_names.append(s.sample_ID)
            except:
                pass
        
        return [NCV_pass], [NCV_pass_names]

    def make_cov_plot_data(self):
        cov = Coverage.query.filter(Coverage.batch_id == self.batch_id) 
        x_axis = range(1,23)
        self.coverage_plot['x_axis'] = x_axis
        for samp in cov:
            self.coverage_plot['samples'][samp.sample_ID] = {'cov':[], 'samp_id':[samp.sample_ID]}
            for i in x_axis:
                self.coverage_plot['samples'][samp.sample_ID]['cov'].append(float(samp.__dict__['Chr'+str(i)+'_Coverage']))

    def make_X_labels(self):
        X_labels = [s.__dict__['sample_ID'] for s in self.cases]
        return X_labels

    def make_NCV_stat(self):
        for chrom in self.NCV_stat.keys():
            NCV_pass , NCV_pass_names = self.make_approved_stats(chrom)
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
                'NCV_pass' : NCV_pass,
                'NCV_pass_names' : NCV_pass_names}

    def make_chrom_abn(self):
        x = 1
        status_x = {'Probable':0.1,'Verified':0.2,'False Positive':0.3,'False Negative':0.4}
        for status in self.sample_state_dict.keys():
            
            self.tris_abn[status] = {'NCV' : [], 's_name' : [], 'x_axis': []}
        for abn in ['13','18','21']:
            for status in self.sample_state_dict.keys():                                      
                self.tris_chrom_abn[abn][status] = {'NCV' : [], 's_name' : [], 'x_axis': []}             
                for s in Sample.query.filter(Sample.__dict__['status_T'+abn] == status):
                    NCV_val = NCV.query.filter_by(sample_ID = s.sample_ID).first().__dict__['NCV_' + abn]
                    self.tris_abn[status]['NCV'].append(float(NCV_val))
                    self.tris_abn[status]['s_name'].append(s.sample_ID)
                    self.tris_abn[status]['x_axis'].append(x+status_x[status])
                    self.tris_chrom_abn[abn][status]['NCV'].append(float(NCV_val))
                    self.tris_chrom_abn[abn][status]['s_name'].append(s.sample_ID)
                    self.tris_chrom_abn[abn][status]['x_axis'].append(0)
            x = x+1
        for abn in self.sex_chrom_abn.keys():
            for status in self.sample_state_dict.keys():                                       
                self.sex_chrom_abn[abn][status] = {'NCV_X' : [], 'NCV_Y' : [], 's_name' : []}             
                for s in Sample.query.filter(Sample.__dict__['status_'+abn] == status):
                    NCV_db = NCV.query.filter_by(sample_ID = s.sample_ID).first()
                    self.sex_chrom_abn[abn][status]['NCV_X'].append(float(NCV_db.NCV_X))
                    self.sex_chrom_abn[abn][status]['NCV_Y'].append(float(NCV_db.NCV_Y))
                    self.sex_chrom_abn[abn][status]['s_name'].append(s.sample_ID)


###---------------- ROUTS ------------------###

@app.route('/login/')
def login():
    print 'DD'
    callback_url = url_for('authorized', _external = True)
    return google.authorize(callback=callback_url)


@app.route('/submit/')
@login_required
def submit():
    print 'SS'
    return render_template('submit.html') 


@app.route('/message', methods=['POST'])
@login_required
def message():
    name = request.form['name']
    email = request.form['email']
    message = request.form['message']
    body = '\n\n'.join(['Submitted Message: ' + message,
                        'Submitted Name: ' + name,
                        'Submitted Mail: ' + email,
                        'Loged in user: '+current_user.email])
    msg = Message(subject = 'NIPT-support',
                    body = body,
                    sender = email,
                    cc = [email, current_user.email],
                    recipients=[ 'mayabrandi@gmail.com'])#'clinicalsupport@clinical-scilifelab.supportsystem.com'])
    mail.send(msg)
    return redirect(url_for('submit_status'))


@app.route('/submit_status/')
@login_required
def submit_status():
    return render_template('submit_status.html')


@app.route('/')
def index():
    print 'AA'
    return render_template('index.html')


@login_manager.user_loader
def load_user(user_id):
    print 'BB'
    """Returns the currently active user as an object."""
    return User.query.filter_by(id=user_id).first()


@app.route('/logout/')
@login_required
def logout():
    print 'CC'
    logout_user()
    session.pop('google_token', None)
    flash('Logged out', 'success')
    return redirect(url_for('/'))

@google.tokengetter
def get_google_token():
    print 'EE'
    """Returns a tuple of Google tokens, if they exist"""
    return session.get('google_token')

@app.route('/authorized')
@google.authorized_handler
def authorized(oauth_response):
    if oauth_response is None:
        flash("Access denied: reason={} error={}"
              .format(request.args['error_reason'],
                      request.args['error_description']))
        return abort(403)
    elif isinstance(oauth_response, OAuthException):
        #current_app.logger.warning(oauth_response.message)
        flash("{} - try again!".format(oauth_response.message))
        return redirect(url_for('/'))

    # add token to session, do it before validation to be able to fetch
    # additional data (like email) on the authenticated user
    session['google_token'] = (oauth_response['access_token'], '')

    # get additional user info with the access token
    google_user = google.get('userinfo') ## get google token
    google_data = google_user.data

    # match email against whitelist before completing sign up
    try:   
        user_obj =  User.query.filter_by(email = google_data['email']).first()
    except:
        user_obj = None
    if user_obj:
        try:
            if login_user(user_obj):
                return redirect(request.args.get('next') or url_for('batch'))
        except:
            flash('Sorry, you could not log in', 'warning')
    else:
        print 'F4'
        flash('Your email is not on the whitelist, contact an admin.')
        return redirect('index')
    if login_user(user_obj):
        return redirect(request.args.get('next') or url_for('batch'))
        print 'F5'
    return redirect('index')

############

@app.route('/NIPT/')
@login_required
def batch():
    NCV_db = NCV.query
    sample_db = Sample.query
    DC = DataClasifyer()
    DC.handle_NCV(NCV_db)
    DC.get_warnings(sample_db)
    return render_template('start_page.html', 
        batches = Batch.query,
        samples = Sample.query,
        NCV_warnings = DC.NCV_warnings)



@app.route('/update', methods=['POST'])
def update():
    user = request.form['current_user']
    dt = datetime.now()
    if 'All samples' in request.form:
        samples = request.form['All samples'].split(',')
        for sample_id in samples:
            sample = NCV.query.filter_by(sample_ID = sample_id).first()
            if not sample.include:
                sample.change_include_date = ' '.join([user,dt.strftime('%Y/%m/%d %H:%M:%S')]) 
            sample.include = True
            db.session.add(sample)
    elif 'sample_ids' in request.form:
        all_samples = request.form['sample_ids'].split(',')
        for sample_id in all_samples:
            sample = NCV.query.filter_by(sample_ID = sample_id).first()
            if sample_id in request.form:
                if not sample.include:
                    sample.change_include_date = ' '.join([user,dt.strftime('%Y/%m/%d %H:%M:%S')])
                sample.include = True
            else:
                if sample.include:
                    sample.change_include_date = ' '.join([user,dt.strftime('%Y/%m/%d %H:%M:%S')])
                sample.include = False
    db.session.commit()
    return redirect(request.referrer)

@app.route('/NIPT/<batch_id>/<sample_id>/update_trisomi_status', methods=['POST'])
@login_required
def update_trisomi_status(batch_id, sample_id):
    dt = datetime.now()  
    sample = Sample.query.filter_by(sample_ID = sample_id).first()
    user = request.form['current_user']
## Wont work.... 
#    chr_abn = ['T13','T18', 'T21', 'X0', 'XXX','XXY','XYY']     
#    for abn in chr_abn:
        #sample.__dict__["comment_"+abn] = request.form["comment_"+abn]
#        sample.__dict__["status_"+abn] = request.form[abn]
#        sample.__dict__["status_change_"+abn] = dt.strftime('%Y/%m/%d %H:%M:%S')

    if sample.status_T13 != request.form['T13']:
        sample.status_T13 = request.form['T13']
        sample.status_change_T13 = ' '.join([user,dt.strftime('%Y/%m/%d %H:%M:%S')])
    if sample.comment_T13 != request.form["comment_T13"]:
        sample.comment_T13 = request.form["comment_T13"]
        sample.status_change_T13 = ' '.join([user,dt.strftime('%Y/%m/%d %H:%M:%S')])

    if sample.status_T18 != request.form['T18']:
        sample.status_T18 = request.form['T18']
        sample.status_change_T18 = ' '.join([user,dt.strftime('%Y/%m/%d %H:%M:%S')])
    if sample.comment_T18 != request.form["comment_T18"]:
        sample.comment_T18 = request.form["comment_T18"]
        sample.status_change_T18 = ' '.join([user,dt.strftime('%Y/%m/%d %H:%M:%S')])

    if sample.status_T21 != request.form['T21']:
        sample.status_T21 = request.form['T21']
        sample.status_change_T21 = ' '.join([user,dt.strftime('%Y/%m/%d %H:%M:%S')])
    if sample.comment_T21 != request.form["comment_T21"]:
        sample.comment_T21 = request.form["comment_T21"]
        sample.status_change_T21 = ' '.join([user,dt.strftime('%Y/%m/%d %H:%M:%S')])

    if sample.status_X0 != request.form['X0']:
        sample.status_change_X0 = ' '.join([user,dt.strftime('%Y/%m/%d %H:%M:%S')])
        sample.status_X0 = request.form['X0']
    if sample.comment_X0 != request.form["comment_X0"]:
        sample.comment_X0 = request.form["comment_X0"]
        sample.status_change_X0 = ' '.join([user,dt.strftime('%Y/%m/%d %H:%M:%S')])

    if sample.status_XXX != request.form['XXX']:
        sample.status_change_XXX =' '.join([user,dt.strftime('%Y/%m/%d %H:%M:%S')])
        sample.status_XXX = request.form['XXX']
    if sample.comment_XXX != request.form["comment_XXX"]:
        sample.comment_XXX = request.form["comment_XXX"]
        sample.status_change_XXX = ' '.join([user,dt.strftime('%Y/%m/%d %H:%M:%S')])

    if sample.status_XXY != request.form['XXY']:
        sample.status_change_XXY = ' '.join([user,dt.strftime('%Y/%m/%d %H:%M:%S')])
        sample.status_XXY = request.form['XXY']
    if sample.comment_XXY != request.form["comment_XXY"]:
        sample.comment_XXY = request.form["comment_XXY"]
        sample.status_change_XXY = ' '.join([user,dt.strftime('%Y/%m/%d %H:%M:%S')])

    if sample.status_XYY != request.form['XYY']:
        sample.status_change_XYY = ' '.join([user,dt.strftime('%Y/%m/%d %H:%M:%S')])
        sample.status_XYY = request.form['XYY']
    if sample.comment_XYY != request.form["comment_XYY"]:
        sample.comment_XYY = request.form["comment_XYY"]
        sample.status_change_XYY = ' '.join([user,dt.strftime('%Y/%m/%d %H:%M:%S')])

    db.session.add(sample)
    db.session.commit()
    return redirect(request.referrer)

@app.route('/NIPT/samples/<sample_id>/')
@login_required
def sample_page( sample_id):
    sample = Sample.query.filter_by(sample_ID = sample_id).first()
    batch_id = sample.batch_id
    DC = DataClasifyer()
    NCV_dat = NCV.query.filter_by(sample_ID = sample_id).first()
    chrom_abnorm = ['T13','T18', 'T21', 'X0', 'XXX','XXY','XYY']
    db_entries = {c:sample.__dict__['status_'+c].replace('\r\n', '').strip() for c in chrom_abnorm }
    db_entries_change = {c:sample.__dict__['status_change_'+c]  for c in chrom_abnorm}              
    db_entries_comments = {c : sample.__dict__['comment_'+c]  for c in chrom_abnorm}
    PP = PlottPage(batch_id)
    PP.make_NCV_stat()
    PP.make_chrom_abn()
    sample_state_dict = PP.sample_state_dict
    for state in sample_state_dict:
        sample_state_dict[state]['T_13'] = Sample.query.filter_by(status_T13 = state)
        sample_state_dict[state]['T_18'] = Sample.query.filter_by(status_T18 = state)
        sample_state_dict[state]['T_21'] = Sample.query.filter_by(status_T21 = state)
    return render_template('sample_page.html',
            NCV_dat = NCV_dat,
            tris_abn = PP.tris_abn,
            sex_chrom_abn = PP.sex_chrom_abn,
            sample = sample, 
            batch_id = batch_id,
            nr_validation_samps = PP.nr_validation_samps,
            sample_id = sample_id,
            chrom_abnorm = chrom_abnorm,
            db_entries = db_entries,
            db_entries_comments = db_entries_comments,
            db_entries_change = db_entries_change,
            NCV_stat = PP.NCV_stat,
            NCV_131821 = ['NCV_13', 'NCV_18', 'NCV_21'],
            state_dict = sample_state_dict,
            sex_tresholds = DC.sex_tresholds,
            tris_thresholds = DC.tris_thresholds)

@app.route('/NIPT/batches/<batch_id>/')
@login_required
def sample(batch_id):
    NCV_db = NCV.query.filter(NCV.batch_id == batch_id)
    sample_db = Sample.query.filter(Sample.batch_id == batch_id)
    DC = DataClasifyer()
    DC.handle_NCV(NCV_db)
    DC.get_warnings(sample_db)
    PP = PlottPage(batch_id)
    PP.make_NCV_stat()
    PP.make_chrom_abn()
    PP.make_cov_plot_data()
    state_dict = {'Probable':{},'False Positive':{},'Verified':{}}
    for state in state_dict:
        state_dict[state]['T_13'] = Sample.query.filter_by(status_T13 = state)
        state_dict[state]['T_18'] = Sample.query.filter_by(status_T18 = state)
        state_dict[state]['T_21'] = Sample.query.filter_by(status_T21 = state)
    return render_template('batch_page.html',
        samples         = Sample.query.filter(Sample.batch_id == batch_id),
        NCV_samples     = NCV.query.filter(NCV.batch_id == batch_id),
        batch_id        = batch_id,
        NCV_stat        = PP.NCV_stat,
        nr_validation_samps = PP.nr_validation_samps,
        NCV_131821      = ['NCV_13', 'NCV_18', 'NCV_21'],
        samp_range      = range(len(PP.NCV_stat['NCV_X']['NCV_cases'])),
        state_dict      = state_dict,
        tris_chrom_abn  = PP.tris_chrom_abn,
        sex_chrom_abn   = PP.sex_chrom_abn,
        sex_tresholds   = DC.sex_tresholds,
        tris_thresholds = DC.tris_thresholds,
        seq_warning = DC.warnings,
        warnings = DC.NCV_warnings,
        NCV_rounded = DC.NCV_data,
        samp_cov_db = PP.coverage_plot,
        sample_ids = ','.join(sample.sample_ID for sample in NCV_db))



def main():
    ssl(app)
    db.init_app(app)
    logging.basicConfig(filename = 'NIPT_log', level=logging.INFO)
    app.run(ssl_context = ctx, host='0.0.0.0', port=8082)    

if __name__ == "__main__":
    main()


