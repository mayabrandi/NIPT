# encoding: utf-8
from flask import make_response, flash, abort, url_for, redirect, render_template, request, session
from flask_login import login_user,logout_user, current_user, login_required
from flask.ext.mail import Message
from flask_oauthlib.client import OAuthException
from sqlalchemy import and_

from database import User, Sample, Batch, Coverage, NCV, BatchStat, db
from extentions import login_manager, google, app, mail
import logging
import os
from datetime import datetime
from views_utils import CoveragePlot, TrisAbnormality, SexAbnormality, BatchDataFilter, DataBaseToCSV, DataClasifyer, Statistics, FetalFraction, CovXCovY, Layout
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
    ncv_columns = ['include', 'comment','sample_name']
    sample_columns = ['T13','T18', 'T21', 'X0', 'XXX','XXY','XYY']
    filter_dict = dict.fromkeys(ncv_columns+sample_columns+['batch'],'')

    # making filters
    ncv_filters = []
    sample_filters = []
    batch_filter = []
    if not request.args.get('clear_filters'):
        batch = request.args.get('batch')
        if batch:
            batch_filter.append(Batch.batch_name.contains(str(batch)))
            filter_dict['batch'] = batch
        for column in ncv_columns:  
            NCV_filter = request.args.get(column)
            if NCV_filter:
                filter_dict[column] = NCV_filter
                if column in ['include']:
                    ncv_filters.append(NCV.__dict__[column] == NCV_filter)
                else:
                    ncv_filters.append(NCV.__dict__[column].contains(str(NCV_filter)))
        for column in sample_columns:
            NCV_filter = request.args.get(column)
            if NCV_filter:
                filter_dict[column] = NCV_filter
                sample_filters.append(Sample.__dict__['status_'+ column] == NCV_filter)
    
    # filtering
    NCV_db = NCV.query
    if ncv_filters:
        NCV_db = NCV_db.filter(and_(* ncv_filters))
    if sample_filters:
        NCV_db = NCV_db.join(Sample).filter(and_(* sample_filters))
    if batch_filter:
        NCV_db = NCV_db.join(Batch).filter(and_(* batch_filter))    
    if not (ncv_filters or sample_filters or batch_filter):
        # show first 50
        NCV_db = NCV.query.all()[0:50]
    else:
        NCV_db = NCV_db.all()
    
    # get clasifications 
    DC = DataClasifyer(NCV_db)
    DC.handle_NCV()

    return render_template('samples.html',
        abn_status_list = ['Other','False Positive','Suspected', 'Probable', 'Verified','Failed'],
        chrom_abnorm = sample_columns,
        nr_included_samps = NCV.query.filter(NCV.include).count(),
        NCV_db  = NCV_db,
        NCV_sex = DC.NCV_sex,
        NCV_warnings = DC.NCV_classified,
        filter_dict = filter_dict
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
    if current_user.role == 'RW':
        db.session.commit()
    else:
        return '', 201
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

    if current_user.role == 'RW':
        db.session.add(sample)
        db.session.commit()
        return redirect(request.referrer)
    else:
        return '', 201
    

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
        current_user       = current_user,
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
        current_user       = current_user,
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
    L = Layout()
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
    SA = SexAbnormality(batch_id, NCV_dat)
    SA.make_case_data('NCV_X', control_normal_X)
    SA.make_case_data('NCV_Y', control_normal_Y)
    SA.make_sex_chrom_abn()
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
        sex_chrom_abn   = SA.sex_chrom_abn,
        case_size       = L.case_size,
        abn_size        = L.abn_size,
        abn_symbol      = L.abn_symbol,
        abn_line        = L.abn_line,
        abn_status_list = ['Other','False Positive','Suspected', 'Probable', 'Verified'],
        ncv_abn_colors  = L.ncv_abn_colors,
        case_data        = SA.case_data,
        sex_tresholds   = DC.sex_tresholds)


@app.route('/NIPT/samples/<sample_id>/tris_plot')
@login_required
def sample_tris_plot( sample_id):
    L = Layout()
    sample = Sample.query.filter_by(sample_ID = sample_id).first()
    NCV_dat = NCV.query.filter_by(sample_ID = sample_id)

    batch_id = sample.batch_id
    batch = Batch.query.filter_by(batch_id = batch_id).first()
    batch_stat =  BatchStat.query.filter(BatchStat.batch_id == batch_id).first()

    DC = DataClasifyer(NCV_dat)
    DC.handle_NCV()

    # Getting and formating sample and NCV data for the control samples in the plot
    TA = TrisAbnormality(batch_id, NCV_dat)

    control_normal, control_abnormal_13 = BDF.control_NCV13()
    case_data13 = TA.make_case_data(control_normal, '13')

    control_normal, control_abnormal_18 = BDF.control_NCV18()
    case_data18 = TA.make_case_data(control_normal,'18')

    control_normal, control_abnormal_21 = BDF.control_NCV21()
    case_data21 = TA.make_case_data(control_normal,'21')

    TA.make_tris_abn_sample_page(control_abnormal_13 + control_abnormal_18 + control_abnormal_21)

    case_data = {'NCV_13':case_data13,
                'NCV_18':case_data18,
                'NCV_21':case_data21}

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
        batch_stat    = batch_stat,
        tris_abn        = TA.tris_abn,
        case_size       = L.case_size,
        abn_size        = L.abn_size,
        abn_symbol      = L.abn_symbol,
        abn_line        = L.abn_line,
        abn_status_list = ['Other','False Positive','Suspected', 'Probable', 'Verified','False Negative'],
        ncv_abn_colors  = L.ncv_abn_colors,
        case_data        = case_data,
        tris_thresholds = DC.tris_thresholds)

@app.route('/NIPT/batches/<batch_id>/NCV13_plot/')
@login_required
def NCV13_plot(batch_id):

    #getting thresholds and layout
    DC = DataClasifyer()
    sample_db = Sample.query.filter(Sample.batch_id == batch_id)
    DC.get_QC_warnings(sample_db)
    L = Layout(batch_id)

    # Getting and formating sample and NCV data for the control samples in the plot
    control_normal, control_abnormal = BDF.control_NCV13()

    # Getting and formating sample and NCV data for the samples in the batch
    batch = Batch.query.filter(Batch.batch_id == batch_id).first()
    NCV_db = NCV.query.filter(NCV.batch_id == batch_id).all()
    TA = TrisAbnormality(batch_id, NCV_db)
    case_data = TA.make_case_data(control_normal, '13')
    tris_chrom_abn = TA.make_tris_chrom_abn(control_abnormal, '13')

    return render_template('batch_page/tab_NCV13.html',
        ##  Warnings Table
        seq_warnings    = DC.QC_warnings,
        ##  Header
        batch_name      = batch.batch_name,
        seq_date        = batch.date,
        batch_id        = batch_id,
        ##  Plotts
        chrom           = '13',
        case_data       = case_data,
        tris_chrom_abn  = tris_chrom_abn,
        case_size       = L.case_size,
        case_line       = L.case_line,
        abn_size        = L.abn_size,
        abn_line        = L.abn_line,
        abn_symbol      = L.abn_symbol,
        ncv_abn_colors  = L.ncv_abn_colors,
        tris_thresholds = DC.tris_thresholds)


@app.route('/NIPT/batches/<batch_id>/NCV18_plot/')
@login_required
def NCV18_plot(batch_id):
    #getting thresholds and layout
    DC = DataClasifyer()
    sample_db = Sample.query.filter(Sample.batch_id == batch_id)
    DC.get_QC_warnings(sample_db)
    L = Layout(batch_id)

    # Getting and formating sample and NCV data for the control samples in the plot
    control_normal, control_abnormal = BDF.control_NCV18()

    # Getting and formating sample and NCV data for the samples in the batch
    batch = Batch.query.filter(Batch.batch_id == batch_id).first()
    NCV_db = NCV.query.filter(NCV.batch_id == batch_id).all()
    TA = TrisAbnormality(batch_id, NCV_db)
    case_data = TA.make_case_data(control_normal, '18')
    tris_chrom_abn = TA.make_tris_chrom_abn(control_abnormal, '18')

    return render_template('batch_page/tab_NCV18.html',
        ##  Warnings Table
        seq_warnings    = DC.QC_warnings,
        ##  Header
        batch_name      = batch.batch_name,
        seq_date        = batch.date,
        batch_id        = batch_id,
        ##  Plotts
        chrom           = '18',
        case_data       = case_data,
        tris_chrom_abn  = tris_chrom_abn,
        case_size       = L.case_size,
        case_line       = L.case_line,
        abn_size        = L.abn_size,
        abn_line        = L.abn_line,
        abn_symbol      = L.abn_symbol,
        ncv_abn_colors  = L.ncv_abn_colors,
        tris_thresholds = DC.tris_thresholds)


@app.route('/NIPT/batches/<batch_id>/NCV21_plot/')
@login_required
def NCV21_plot(batch_id):

    #getting thresholds and layout
    DC = DataClasifyer()
    sample_db = Sample.query.filter(Sample.batch_id == batch_id)
    DC.get_QC_warnings(sample_db)
    L = Layout(batch_id)

    # Getting and formating sample and NCV data for the control samples in the plot
    control_normal, control_abnormal = BDF.control_NCV21()

    # Getting and formating sample and NCV data for the samples in the batch
    batch = Batch.query.filter(Batch.batch_id == batch_id).first()
    NCV_db = NCV.query.filter(NCV.batch_id == batch_id).all()
    TA = TrisAbnormality(batch_id, NCV_db)
    case_data = TA.make_case_data(control_normal, '21')
    tris_chrom_abn = TA.make_tris_chrom_abn(control_abnormal, '21')

    return render_template('batch_page/tab_NCV21.html',
        ##  Warnings Table
        seq_warnings    = DC.QC_warnings,
        ##  Header
        batch_name      = batch.batch_name,
        seq_date        = batch.date,
        batch_id        = batch_id,
        ##  Plotts
        chrom           = '21',
        case_data       = case_data,
        tris_chrom_abn  = tris_chrom_abn,
        case_size       = L.case_size,
        case_line       = L.case_line,
        abn_size        = L.abn_size,
        abn_line        = L.abn_line,
        abn_symbol      = L.abn_symbol,
        ncv_abn_colors  = L.ncv_abn_colors,
        tris_thresholds = DC.tris_thresholds)

@app.route('/NIPT/batches/<batch_id>/NCVXY_plot/')
@login_required
def NCVXY_plot(batch_id):
    L = Layout(batch_id)

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
    SA = SexAbnormality(batch_id, NCV_db)
    SA.make_case_data('NCV_X', control_normal_X)
    SA.make_case_data('NCV_Y', control_normal_Y)
    SA.make_sex_chrom_abn()
    return render_template('batch_page/tab_NCVXY.html',
        ##  Header
        batch_name      = batch.batch_name,
        seq_date        = batch.date,
        ##  Warnings Table
        seq_warnings    = DC.QC_warnings,
        ##  Plotts
        NCV_pass_names  = control_normal_XY_names,
        case_data        = SA.case_data,
        case_size       = L.case_size,
        case_line       = L.case_line,
        abn_size        = L.abn_size,
        abn_line        = L.abn_line,
        abn_symbol      = L.abn_symbol,
        samp_range      = range(len(SA.case_data['NCV_X']['samples'])),
        sex_chrom_abn   = SA.sex_chrom_abn,
        abn_status_list = ['Other','False Positive','Suspected', 'Probable', 'Verified','False Negative'],
        many_colors     = L.many_colors_dict,
        sex_tresholds   = DC.sex_tresholds,
        ncv_abn_colors  = L.ncv_abn_colors,
        ##  Buttons
        batch_id        = batch_id,
        sample_ids      = ','.join(sample.sample_ID for sample in NCV_db),
        sample_list     = SA.sample_list)

@app.route('/NIPT/batches/<batch_id>/FF_plot/')
@login_required
def FF_plot(batch_id):
    L = Layout(batch_id)
    FF = FetalFraction(batch_id)
    FF.format_case_dict()
    FF.format_contol_dict()
    FF.form_prediction_interval()
    batch = Batch.query.filter(Batch.batch_id == batch_id).first()
    sample_db = Sample.query.filter(Sample.batch_id == batch_id)
    DC = DataClasifyer()
    DC.get_QC_warnings(sample_db)

    return render_template('batch_page/tab_FF.html',
        ##  Warnings Table
        seq_warnings    = DC.QC_warnings,
        ##  Header
        batch_name      = batch.batch_name,
        batch_id        = batch_id,
        seq_date        = batch.date,
        ##  Plotts
        nr_contol_samples = FF.nr_contol_samples,
        predict         = FF.perdiction,
        cases           = FF.samples,
        control         = FF.control,
        case_size       = L.case_size,
        case_line       = L.case_line,
        many_colors     = L.many_colors_dict,
        sample_list     = FF.sample_list
        )

@app.route('/NIPT/batches/<batch_id>/covX_covY/')
@login_required
def covX_covY(batch_id):
    L = Layout(batch_id)
    CC = CovXCovY(batch_id)
    CC.format_case_dict()
    CC.format_contol_dict()
    CC.format_pos_contol()
    batch = Batch.query.filter(Batch.batch_id == batch_id).first()
    sample_db = Sample.query.filter(Sample.batch_id == batch_id)
    DC = DataClasifyer()
    DC.get_QC_warnings(sample_db)

    return render_template('batch_page/tab_covX_covY.html',
        ##  Warnings Table
        seq_warnings    = DC.QC_warnings,
        ##  Header
        batch_name      = batch.batch_name,
        batch_id        = batch_id,
        seq_date        = batch.date,
        ##  Plotts
        nr_contol_samples = CC.nr_contol_samples,
        cases           = CC.samples,
        control         = CC.control,
        pos_contol      = CC.pos_contol,
        case_size       = L.case_size,
        case_line       = L.case_line,
        ncv_abn_colors  = L.ncv_abn_colors,
        abn_size        = L.abn_size,
        abn_line        = L.abn_line,
        abn_symbol      = L.abn_symbol,
        many_colors     = L.many_colors_dict,
        sample_list     = CC.sample_list
        )


@app.route('/NIPT/batches/<batch_id>/coverage_plot/')
@login_required
def coverage_plot(batch_id):
    L = Layout(batch_id)
    NCV_db = NCV.query.filter(NCV.batch_id == batch_id)
    sample_db = Sample.query.filter(Sample.batch_id == batch_id)
    batch = Batch.query.filter(Batch.batch_id == batch_id).first()

    DC = DataClasifyer(NCV_db)
    DC.handle_NCV()
    DC.get_QC_warnings(sample_db)

    CP = CoveragePlot(batch_id)
    CP.make_cov_plot_data()
    return render_template('batch_page/tab_coverage.html',
        ##  Header
        batch_name      = batch.batch_name,
        seq_date        = batch.date,
        ##  Warnings Table
        seq_warnings    = DC.QC_warnings,
        samp_cov_db     = CP.coverage_plot,
        cov_colors      = L.cov_colors,
        case_size       = L.case_size,
        case_line       = L.case_line,
        ##  Buttons
        batch_id        = batch_id,
        sample_ids      = ','.join(sample.sample_ID for sample in NCV_db),
        sample_list     = CP.sample_list)


import json
@app.route('/NIPT/batches/<batch_id>/report/<coverage>')
@login_required
def report(batch_id, coverage):
    L = Layout(batch_id)
    NCV_db = NCV.query.filter(NCV.batch_id == batch_id)
    sample_db = Sample.query.filter(Sample.batch_id == batch_id)
    batch = Batch.query.filter(Batch.batch_id == batch_id).first()
    DC = DataClasifyer(NCV_db)
    DC.handle_NCV()
    DC.make_sex_tresholds(BDF.NCV_passed_X)
    DC.get_QC_warnings(sample_db)
    DC.get_manually_classified(sample_db)

    CP = CoveragePlot(batch_id)
    CP.make_cov_plot_data()

    control_normal_X, control_normal_Y, control_normal_XY_names = BDF.control_NCVXY()
    SA = SexAbnormality(batch_id, NCV_db)
    SA.make_case_data('NCV_X', control_normal_X)
    SA.make_case_data('NCV_Y', control_normal_Y)
    SA.make_sex_chrom_abn()

    TA = TrisAbnormality(batch_id, NCV_db)

    control_normal, control_abnormal = BDF.control_NCV13()
    case_data13 = TA.make_case_data(control_normal, '13')
    tris_chrom_abn13 = TA.make_tris_chrom_abn(control_abnormal, '13')

    control_normal, control_abnormal = BDF.control_NCV18()
    case_data18 = TA.make_case_data(control_normal,'18')
    tris_chrom_abn18 = TA.make_tris_chrom_abn(control_abnormal, '18')

    control_normal, control_abnormal = BDF.control_NCV21()
    case_data21 = TA.make_case_data(control_normal, '21')
    tris_chrom_abn21 = TA.make_tris_chrom_abn(control_abnormal, '21')

    tris_case_data = {'NCV_13':case_data13,
                    'NCV_18':case_data18,
                    'NCV_21':case_data21}
    tris_chrom_abn = {'13':tris_chrom_abn13,
                    '18':tris_chrom_abn18,
                    '21':tris_chrom_abn21}

    CC = CovXCovY(batch_id)
    CC.format_case_dict()
    CC.format_contol_dict()
    CC.format_pos_contol()

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
        case_size       = L.case_size,
        abn_size        = L.abn_size,
        abn_symbol      = L.abn_symbol,
        case_line       = L.case_line,
        abn_line        = L.abn_line,
        cov_colors      = L.cov_colors,
        many_colors     = L.many_colors_dict,
        samp_range      = range(len(SA.case_data['NCV_X']['samples'])),
        tris_chrom_abn  = tris_chrom_abn,
        tris_case_data  = tris_case_data,
        case_data       = SA.case_data, ## i xy-plot
        sex_chrom_abn   = SA.sex_chrom_abn,
        abn_status_list = ['Other','False Positive','Suspected', 'Probable', 'Verified'],
        ncv_abn_colors  = L.ncv_abn_colors,
        sex_tresholds   = DC.sex_tresholds,
        tris_thresholds = DC.tris_thresholds,
        NCV_pass_names  = control_normal_XY_names,
        ##  Coverage
        coverage        = coverage,
        samp_cov_db     = CP.coverage_plot,
        nr_contol_samples = CC.nr_contol_samples,
        cases           = CC.samples,
        control         = CC.control,
        pos_contol      = CC.pos_contol,
        sample_list     = SA.sample_list)




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
        
