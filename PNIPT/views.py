# encoding: utf-8
from flask import make_response, flash, abort, url_for, redirect, render_template, request, session
from flask_login import login_user,logout_user, current_user, login_required
from flask.ext.mail import Message
from flask_oauthlib.client import OAuthException
from database import User, Sample, Batch, Coverage, NCV, BatchStat, db
from extentions import login_manager, google, app, mail
import logging
import os
from datetime import datetime
from views_utils import PlottPage, BatchDataFilter, DataBaseToCSV, DataClasifyer, Statistics
import time
import json
from datetime import datetime

BDF = BatchDataFilter()

@app.route('/login/')
def login():
    callback_url = url_for('authorized', _external=True)
    return google.authorize(callback=callback_url)


@app.route('/submit/')
@login_required
def submit():
    return render_template('new_user_page.html') 


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
    return render_template('index.html')


@login_manager.user_loader
def load_user(user_id):
    """Returns the currently active user as an object."""
    return User.query.filter_by(id=user_id).first()


@app.route('/logout/')
@login_required
def logout():
    logout_user()
    session.pop('google_token', None)
    return redirect(url_for('index'))

@google.tokengetter
def get_google_token():
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
        return redirect(url_for('index'))

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
        flash('Your email is not on the whitelist, contact an admin.')
        return redirect(url_for('index'))
    if login_user(user_obj):
        return redirect(request.args.get('next') or url_for('batch'))
    return redirect(url_for('index'))


@app.route('/NIPT/samples')
@login_required
def samples():
#    import ipdb; ipdb.set_trace()
    NCV_db = NCV.query
    sample_db = Sample.query
    DC = DataClasifyer(NCV_db)
    DC.handle_NCV()
    DC.get_manually_classified(sample_db)
    return render_template('samples_page.html',
        nr_included_samps = NCV.query.filter(NCV.include).count(),
        NCV_db  = sample_db,
        NCV_sex = DC.NCV_sex,
        sample_names = DC.sample_names,
        NCV_man_class = DC.man_class,
        NCV_warnings = DC.NCV_classified,
        NCV_comment = DC.NCV_comment,
        NCV_included = DC.NCV_included,
        batch_info = DC.batch
        )

@app.route('/NIPT/')
@login_required
def batch():
    sample_db = Sample.query
    return render_template('start_page.html', 
        batches = Batch.query)

@app.route('/download')
def download():
    DB2CSV = DataBaseToCSV()
    DB2CSV.get_dict_data()
    csvData = DB2CSV.WriteDictToCSV()
    response = make_response(csvData)
    response.headers["Content-Disposition"] = "attachment; filename=NIPT_db.csv"
    return response

@app.route('/update', methods=['POST'])
def update():
    if 'current_user' in request.form:
        user = request.form['current_user']
    else:
        user = 'unknown'
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
    if 'sample_ids' in request.form:
        all_samples = request.form['sample_ids'].split(',')
        for sample_id in all_samples:
            sample = NCV.query.filter_by(sample_ID = sample_id).first()
            samp_comment = 'comment_'+sample_id
            if samp_comment in request.form:
                if request.form[samp_comment] != sample.comment:
                    sample.comment = request.form[samp_comment]
                    sample.change_include_date = ' '.join([user,dt.strftime('%Y/%m/%d %H:%M:%S')])
    if 'comment' in request.form:
        sample_id = request.form['sample_id']
        sample = NCV.query.filter_by(sample_ID = sample_id).first()
        if request.form['comment'] != sample.comment:
            sample.comment = request.form['comment']
    db.session.commit()
    return redirect(request.referrer)




@app.route('/NIPT/<batch_id>/<sample_id>/update_trisomi_status', methods=['POST'])
@login_required
def update_trisomi_status(batch_id, sample_id):
    dt = datetime.now()  
    sample = Sample.query.filter_by(sample_ID = sample_id).first()
    user = request.form['current_user']

    if sample.status_T13 != request.form['T13']:
        sample.status_T13 = request.form['T13']
        sample.status_change_T13 = ' '.join([user,dt.strftime('%Y/%m/%d %H:%M:%S')])
    if sample.status_T18 != request.form['T18']:
        sample.status_T18 = request.form['T18']
        sample.status_change_T18 = ' '.join([user,dt.strftime('%Y/%m/%d %H:%M:%S')])
    if sample.status_T21 != request.form['T21']:
        sample.status_T21 = request.form['T21']
        sample.status_change_T21 = ' '.join([user,dt.strftime('%Y/%m/%d %H:%M:%S')])
    if sample.status_X0 != request.form['X0']:
        sample.status_change_X0 = ' '.join([user,dt.strftime('%Y/%m/%d %H:%M:%S')])
        sample.status_X0 = request.form['X0']
    if sample.status_XXX != request.form['XXX']:
        sample.status_change_XXX =' '.join([user,dt.strftime('%Y/%m/%d %H:%M:%S')])
        sample.status_XXX = request.form['XXX']
    if sample.status_XXY != request.form['XXY']:
        sample.status_change_XXY = ' '.join([user,dt.strftime('%Y/%m/%d %H:%M:%S')])
        sample.status_XXY = request.form['XXY']
    if sample.status_XYY != request.form['XYY']:
        sample.status_change_XYY = ' '.join([user,dt.strftime('%Y/%m/%d %H:%M:%S')])
        sample.status_XYY = request.form['XYY']

    db.session.add(sample)
    db.session.commit()
    return redirect(request.referrer)

@app.route('/NIPT/batches/<batch_id>/')
@login_required
def sample(batch_id):
    NCV_db = NCV.query.filter(NCV.batch_id == batch_id)
    sample_db = Sample.query.filter(Sample.batch_id == batch_id)
    batch = Batch.query.filter(Batch.batch_id == batch_id).first()
    DC = DataClasifyer(NCV_db)
    DC.handle_NCV()
    DC.get_QC_warnings(sample_db)
    DC.get_manually_classified(sample_db)
    return render_template('batch_page/batch_page.html',
        ##  Header
        batch_name      = batch.batch_name,
        seq_date        = batch.date,
        ##  Warnings Table
        seq_warnings    = DC.QC_warnings,
        ##  NCV Table
        NCV_samples     = NCV.query.filter(NCV.batch_id == batch_id),
        man_class       = DC.man_class_merged,
        NCV_sex         = DC.NCV_sex,
        warnings        = DC.NCV_classified,
        batch_table_data     = DC.NCV_data,
        ##  Coverage
        bool_warns      = filter(None, DC.NCV_classified.values()),
        ##  Buttons
        batch_id        = batch_id,
        sample_ids      = ','.join(sample.sample_ID for sample in NCV_db))


@app.route('/NIPT/samples/<sample_id>/')
@login_required
def sample_page( sample_id):
    sample = Sample.query.filter_by(sample_ID = sample_id).first()
    NCV_dat = NCV.query.filter_by(sample_ID = sample_id)

    batch_id = sample.batch_id
    batch = Batch.query.filter_by(batch_id = batch_id).first()

    DC = DataClasifyer(NCV_dat)
    DC.handle_NCV()

    chrom_abnorm = ['T13','T18', 'T21', 'X0', 'XXX','XXY','XYY']
    db_entries = {c:sample.__dict__['status_'+c].replace('\r\n', '').strip() for c in chrom_abnorm }
    db_entries_change = {c:sample.__dict__['status_change_'+c]  for c in chrom_abnorm}              

    return render_template('sample_page/sample_page.html',
        ## Header & Info Box
        NCV_dat         = NCV_dat.first(),
        sample          = sample,
        batch_id        = batch_id,
        batch_name      = batch.batch_name,
        batch           = batch,
        NCV_sex         = DC.NCV_sex[sample_id],
        NCV_warn        = DC.NCV_classified[sample_id],
        ## Status Table
        sample_id       = sample_id,
        chrom_abnorm    = chrom_abnorm,
        db_entries      = db_entries,
        db_entries_change = db_entries_change)

@app.route('/NIPT/samples/<sample_id>/sex_plot')
@login_required
def sample_xy_plot( sample_id):
    sample = Sample.query.filter_by(sample_ID = sample_id).first()
    NCV_dat = NCV.query.filter_by(sample_ID = sample_id)

    batch_id = sample.batch_id
    batch = Batch.query.filter_by(batch_id = batch_id).first()

    DC = DataClasifyer(NCV_dat)
    DC.handle_NCV()

    DC.make_sex_tresholds(BDF.NCV_passed_X)
    chrom_abnorm = ['T13','T18', 'T21', 'X0', 'XXX','XXY','XYY']

    db_entries = {c:sample.__dict__['status_'+c].replace('\r\n', '').strip() for c in chrom_abnorm }
    db_entries_change = {c:sample.__dict__['status_change_'+c]  for c in chrom_abnorm}

    # Getting and formating sample and NCV data for the control samples in the plot
    control_normal_X, control_normal_Y, control_normal_XY_names = BDF.control_NCVXY()
    PP = PlottPage(batch_id, NCV_dat)
    PP.make_case_data_new('NCV_X', control_normal_X)
    PP.make_case_data_new('NCV_Y', control_normal_Y)
    PP.make_sex_chrom_abn()
    return render_template('sample_page/sample_xy_plot.html',
        ## Header & Info Box
        NCV_dat         = NCV_dat.first(),
        sample_name     = sample.sample_name,
        sample          = sample,
        sample_id       = sample_id,
        batch_id        = batch_id,
        batch_name      = batch.batch_name,
        batch_date      = batch.date,
        NCV_sex         = DC.NCV_sex[sample_id],
        NCV_warn        = DC.NCV_classified[sample_id],
        ## Plots
        tris_abn        = PP.tris_abn,
        sex_chrom_abn   = PP.sex_chrom_abn,
        case_size       = PP.case_size,
        abn_size        = PP.abn_size,
        abn_symbol      = PP.abn_symbol,
        abn_status_list = ['Other','False Positive','Suspected', 'Probable', 'Verified'],
        ncv_abn_colors  = PP.ncv_abn_colors,
        case_data        = PP.case_data,
        NCV_131821      = ['NCV_13', 'NCV_18', 'NCV_21'],
        sex_tresholds   = DC.sex_tresholds,
        tris_thresholds = DC.tris_thresholds,
        tris_chrom_abn  = PP.tris_chrom_abn)


@app.route('/NIPT/samples/<sample_id>/tris_plot')
@login_required
def sample_tris_plot( sample_id):
    sample = Sample.query.filter_by(sample_ID = sample_id).first()
    NCV_dat = NCV.query.filter_by(sample_ID = sample_id)

    batch_id = sample.batch_id
    batch = Batch.query.filter_by(batch_id = batch_id).first()
    DC = DataClasifyer(NCV_dat)
    DC.handle_NCV()

    # Getting and formating sample and NCV data for the control samples in the plot
    PP = PlottPage(batch_id, NCV_dat)

    control_normal, control_abnormal = BDF.control_NCV13()
    PP.make_case_data_new('NCV_13', control_normal)
    PP.make_tris_chrom_abn(control_abnormal, '13')

    control_normal, control_abnormal = BDF.control_NCV18()
    PP.make_case_data_new('NCV_18', control_normal)
    PP.make_tris_chrom_abn(control_abnormal, '18')

    control_normal, control_abnormal = BDF.control_NCV21()
    PP.make_case_data_new('NCV_21', control_normal)
    PP.make_tris_chrom_abn(control_abnormal, '21')

    return render_template('sample_page/sample_tris_plot.html',
        ## Header & Info Box
        NCV_dat         = NCV_dat.first(),
        sample          = sample,
        sample_id       = sample_id,
        batch_id        = batch_id,
        batch_name      = batch.batch_name,
        batch           = batch,
        NCV_sex         = DC.NCV_sex[sample_id],
        NCV_warn        = DC.NCV_classified[sample_id],
        ## Plots
        tris_abn        = PP.tris_abn,
        case_size       = PP.case_size,
        abn_size        = PP.abn_size,
        abn_symbol      = PP.abn_symbol,
        abn_status_list = ['Other','False Positive','Suspected', 'Probable', 'Verified'],
        ncv_abn_colors  = PP.ncv_abn_colors,
        case_data        = PP.case_data,
        tris_thresholds = DC.tris_thresholds,
        tris_chrom_abn  = PP.tris_chrom_abn)

@app.route('/NIPT/batches/<batch_id>/NCV13_plot/')
@login_required
def NCV13_plot(batch_id):

    # Getting and formating sample and NCV data for the samples in the batch
    NCV_db = NCV.query.filter(NCV.batch_id == batch_id)
    sample_db = Sample.query.filter(Sample.batch_id == batch_id)
    batch = Batch.query.filter(Batch.batch_id == batch_id).first()
    DC = DataClasifyer(NCV_db)
    DC.handle_NCV()
    DC.get_QC_warnings(sample_db)


    # Getting and formating sample and NCV data for the control samples in the plot
    control_normal, control_abnormal = BDF.control_NCV13()
    PP = PlottPage(batch_id, NCV_db)
    PP.make_case_data_new('NCV_13', control_normal)
    PP.make_tris_chrom_abn(control_abnormal, '13')
    
    return render_template('batch_page/tab_NCV13.html',
        ##  Header
        batch_name      = batch.batch_name,
        seq_date        = batch.date,
        ##  Warnings Table
        seq_warnings    = DC.QC_warnings,
        ##  Plotts
        chrom           = '13',
        case_data        = PP.case_data['NCV_13'],
        case_size       = PP.case_size,
        abn_size        = PP.abn_size,
        abn_symbol      = PP.abn_symbol,
        tris_chrom_abn  = PP.tris_chrom_abn['13'],
        abn_status_list = ['Other','False Positive','Suspected', 'Probable', 'Verified'],
        ncv_abn_colors  = PP.ncv_abn_colors,
        tris_thresholds = DC.tris_thresholds,
        ##  Coverage
        bool_warns      = filter(None, DC.NCV_classified.values()),
        ##  Buttons
        batch_id        = batch_id,
        sample_ids      = ','.join(sample.sample_ID for sample in NCV_db))


@app.route('/NIPT/batches/<batch_id>/NCV18_plot/')
@login_required
def NCV18_plot(batch_id):
    
    # Getting and formating sample and NCV data for the samples in the batch
    NCV_db = NCV.query.filter(NCV.batch_id == batch_id)
    sample_db = Sample.query.filter(Sample.batch_id == batch_id)
    batch = Batch.query.filter(Batch.batch_id == batch_id).first()
    DC = DataClasifyer(NCV_db)
    DC.handle_NCV()
    DC.get_QC_warnings(sample_db)
    

    # Getting and formating sample and NCV data for the control samples in the plot
    control_normal, control_abnormal = BDF.control_NCV18()
    PP = PlottPage(batch_id, NCV_db)
    PP.make_case_data_new('NCV_18', control_normal)
    PP.make_tris_chrom_abn(control_abnormal, '18')

    return render_template('batch_page/tab_NCV18.html',
        ##  Header
        batch_name      = batch.batch_name,
        seq_date        = batch.date,
        ##  Warnings Table
        seq_warnings    = DC.QC_warnings,
        ##  Plotts
        chrom           = '18',
        case_data        = PP.case_data['NCV_18'],
        case_size       = PP.case_size,
        abn_size        = PP.abn_size,
        abn_symbol      = PP.abn_symbol,
        tris_chrom_abn  = PP.tris_chrom_abn['18'],
        abn_status_list = ['Other','False Positive','Suspected', 'Probable', 'Verified'],
        ncv_abn_colors  = PP.ncv_abn_colors,
        tris_thresholds = DC.tris_thresholds,
        ##  Coverage
        bool_warns      = filter(None, DC.NCV_classified.values()),
        ##  Buttons
        batch_id        = batch_id,
        sample_ids      = ','.join(sample.sample_ID for sample in NCV_db))


@app.route('/NIPT/batches/<batch_id>/NCV21_plot/')
@login_required
def NCV21_plot(batch_id):

    # Getting and formating sample and NCV data for the samples in the batch
    NCV_db = NCV.query.filter(NCV.batch_id == batch_id)
    sample_db = Sample.query.filter(Sample.batch_id == batch_id)
    batch = Batch.query.filter(Batch.batch_id == batch_id).first()
    DC = DataClasifyer(NCV_db)
    DC.handle_NCV()
    DC.get_QC_warnings(sample_db)


    # Getting and formating sample and NCV data for the control samples in the plot
    control_normal, control_abnormal = BDF.control_NCV21()
    PP = PlottPage(batch_id, NCV_db)
    PP.make_case_data_new('NCV_21', control_normal)
    PP.make_tris_chrom_abn(control_abnormal, '21')

    return render_template('batch_page/tab_NCV21.html',
        ##  Header
        batch_name      = batch.batch_name,
        seq_date        = batch.date,
        ##  Warnings Table
        seq_warnings    = DC.QC_warnings,
        ##  Plotts
        chrom           = '21',
        case_data        = PP.case_data['NCV_21'],
        case_size       = PP.case_size,
        abn_size        = PP.abn_size,
        abn_symbol      = PP.abn_symbol,
        tris_chrom_abn  = PP.tris_chrom_abn['21'],
        abn_status_list = ['Other','False Positive','Suspected', 'Probable', 'Verified'],
        ncv_abn_colors  = PP.ncv_abn_colors,
        tris_thresholds = DC.tris_thresholds,
        ##  Coverage
        bool_warns      = filter(None, DC.NCV_classified.values()),
        ##  Buttons
        batch_id        = batch_id,
        sample_ids      = ','.join(sample.sample_ID for sample in NCV_db))

@app.route('/NIPT/batches/<batch_id>/NCVXY_plot/')
@login_required
def NCVXY_plot(batch_id):

    # Getting and formating sample and NCV data for the samples in the batch
    NCV_db = NCV.query.filter(NCV.batch_id == batch_id)
    sample_db = Sample.query.filter(Sample.batch_id == batch_id)
    batch = Batch.query.filter(Batch.batch_id == batch_id).first()
    DC = DataClasifyer(NCV_db)
    DC.handle_NCV()
    DC.make_sex_tresholds(BDF.NCV_passed_X)
    DC.get_QC_warnings(sample_db)


    # Getting and formating sample and NCV data for the control samples in the plot
    control_normal_X, control_normal_Y, control_normal_XY_names = BDF.control_NCVXY() 
    PP = PlottPage(batch_id, NCV_db)
    PP.make_case_data_new('NCV_X', control_normal_X)
    PP.make_case_data_new('NCV_Y', control_normal_Y)
    PP.make_sex_chrom_abn()
    PP.make_cov_plot_data()
    return render_template('batch_page/tab_NCVXY.html',
        ##  Header
        batch_name      = batch.batch_name,
        seq_date        = batch.date,
        ##  Warnings Table
        seq_warnings    = DC.QC_warnings,
        ##  Plotts
        NCV_pass_names  = control_normal_XY_names,
        case_data        = PP.case_data,
        case_size       = PP.case_size,
        abn_size        = PP.abn_size,
        abn_symbol      = PP.abn_symbol,
        samp_range      = range(len(PP.case_data['NCV_X']['NCV_cases'])),
        sex_chrom_abn   = PP.sex_chrom_abn,
        abn_status_list = ['Other','False Positive','Suspected', 'Probable', 'Verified'],
        many_colors     = PP.many_colors,
        sex_tresholds   = DC.sex_tresholds,
        ncv_abn_colors  = PP.ncv_abn_colors,
        ##  Coverage
        bool_warns      = filter(None, DC.NCV_classified.values()),
        ##  Buttons
        batch_id        = batch_id,
        sample_ids      = ','.join(sample.sample_ID for sample in NCV_db))

@app.route('/NIPT/batches/<batch_id>/coverage_plot/')
@login_required
def coverage_plot(batch_id):
    NCV_db = NCV.query.filter(NCV.batch_id == batch_id)
    sample_db = Sample.query.filter(Sample.batch_id == batch_id)
    batch = Batch.query.filter(Batch.batch_id == batch_id).first()

   # from sqlalchemy import func
   # query = Sample.query.filter(func.or_(
   #     Sample.sample_name.like(f"%{query}%"),
   #     Batch.batch_name.like(f"%{query}%)
   # ))

    DC = DataClasifyer(NCV_db)
    DC.handle_NCV()
    DC.get_QC_warnings(sample_db)
    PP = PlottPage(batch_id, BDF)
    PP.make_cov_plot_data()
    return render_template('batch_page/tab_coverage.html',
        ##  Header
        batch_name      = batch.batch_name,
        seq_date        = batch.date,
        ##  Warnings Table
        seq_warnings    = DC.QC_warnings,
        ##  Coverage
        bool_warns      = filter(None, DC.NCV_classified.values()),
        samp_cov_db     = PP.coverage_plot,
        cov_colors      = PP.cov_colors,
        ##  Buttons
        batch_id        = batch_id,
        sample_ids      = ','.join(sample.sample_ID for sample in NCV_db))


import json
@app.route('/NIPT/batches/<batch_id>/report')
@login_required
def report(batch_id):
    NCV_db = NCV.query.filter(NCV.batch_id == batch_id)
    sample_db = Sample.query.filter(Sample.batch_id == batch_id)
    batch = Batch.query.filter(Batch.batch_id == batch_id).first()
    DC = DataClasifyer(NCV_db)
    DC.handle_NCV()
    DC.make_sex_tresholds(BDF.NCV_passed_X)
    DC.get_QC_warnings(sample_db)
    DC.get_manually_classified(sample_db)
    control_normal_X, control_normal_Y, control_normal_XY_names = BDF.control_NCVXY()
    PP = PlottPage(batch_id, NCV_db)
    PP.make_case_data_new('NCV_X', control_normal_X)
    PP.make_case_data_new('NCV_Y', control_normal_Y)
    PP.make_sex_chrom_abn()

    control_normal, control_abnormal = BDF.control_NCV13()
    PP.make_case_data_new('NCV_13', control_normal)
    PP.make_tris_chrom_abn(control_abnormal, '13')
    control_normal, control_abnormal = BDF.control_NCV18()
    PP.make_case_data_new('NCV_18', control_normal)
    PP.make_tris_chrom_abn(control_abnormal, '18')
    control_normal, control_abnormal = BDF.control_NCV21()
    PP.make_case_data_new('NCV_21', control_normal)
    PP.make_tris_chrom_abn(control_abnormal, '21')

    PP.make_cov_plot_data()
    ST = Statistics()
    ST.get_20_latest()
    return render_template('batch_page/report_page.html',
        ##  Header
        batch_name      = batch.batch_name,
        ##  Warnings Table
        seq_warnings    = DC.QC_warnings,
        ##  NCV Table
        NCV_samples     = NCV.query.filter(NCV.batch_id == batch_id),
        man_class       = DC.man_class_merged,
        NCV_sex         = DC.NCV_sex,
        warnings        = DC.NCV_classified,
        batch_table_data     = DC.NCV_data,
        ##  Plotts
        batch_names     = ST.batch_names,
        thresholds      = ST.thresholds,
        batch_ids       = ST.batch_ids,
        case_data        =PP.case_data,
        case_size       = PP.case_size,
        abn_size        = PP.abn_size,
        abn_symbol      = PP.abn_symbol,
        samp_range      = range(len(PP.case_data['NCV_X']['NCV_cases'])),
        tris_chrom_abn  = PP.tris_chrom_abn,
        sex_chrom_abn   = PP.sex_chrom_abn,
        abn_status_list = ['Other','False Positive','Suspected', 'Probable', 'Verified'],
        cov_colors      = PP.cov_colors,
        many_colors     = PP.many_colors,
        ncv_abn_colors  = PP.ncv_abn_colors,
        sex_tresholds   = DC.sex_tresholds,
        tris_thresholds = DC.tris_thresholds,
        NCV_pass_names  = control_normal_XY_names,
        ##  Coverage
        bool_warns      = filter(None, DC.NCV_classified.values()),
        samp_cov_db     = PP.coverage_plot)




@app.route('/NIPT/statistics/')
@login_required
def statistics():
    ST = Statistics()
    ST.get_20_latest()
    ST.make_PCS()
    ST.make_Stdev()
    ST.make_statistics_from_database_Sample()
    ST.make_statistics_from_database_NCV()
    return render_template('statistics_page.html',
        ticks = range(1,len(ST.NonExcludedSites2Tags)+1),
        NonExcludedSites2Tags = ST.NonExcludedSites2Tags,
        GCBias = ST.GCBias,
        Ratio_13 = ST.Ratio_13,
        Ratio_18 = ST.Ratio_18,
        Ratio_21 = ST.Ratio_21,
        Stdev_13 = ST.Stdev_13,
        Stdev_18 = ST.Stdev_18,
        Stdev_21 = ST.Stdev_21,
        Clusters = ST.Clusters,
        NonExcludedSites = ST.NonExcludedSites,
        PerfectMatchTags2Tags = ST.PerfectMatchTags2Tags,
        FF_Formatted = ST.FF_Formatted,
        NCD_Y = ST.NCD_Y,
        PCS = ST.PCS,
        thresholds = ST.thresholds,
        Library_nM = ST.Library_nM,
        Tags2IndexedReads = ST.Tags2IndexedReads,
        TotalIndexedReads2Clusters = ST.TotalIndexedReads2Clusters,
        batch_ids = ST.batch_ids,
        batch_names = ST.batch_names,
        dates = ST.dates)
        
