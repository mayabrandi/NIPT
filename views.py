# encoding: utf-8
from flask import flash, abort, url_for, redirect, render_template, request, session
from flask_login import login_user,logout_user, current_user, login_required
from flask.ext.mail import Message
from flask_oauthlib.client import OAuthException
from database import User, Sample, Batch, Coverage, NCV, BatchStat, db
from extentions import login_manager, google, app, mail, ssl, ctx
import logging
import os
from datetime import datetime
from views_utils import DataHandler, DataClasifyer, PlottPage, Statistics



@app.route('/login/')
def login():
    callback_url = url_for('authorized', _external = True)
    return google.authorize(callback=callback_url)


@app.route('/submit/')
@login_required
def submit():
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

@app.route('/NIPT/')
@login_required
def batch():
    NCV_db = NCV.query
    DH = DataHandler()
    sample_db = Sample.query
    DC = DataClasifyer()
    DC.handle_NCV(NCV_db)
    DC.get_QC_warnings(sample_db)
    return render_template('start_page.html', 
        batches = Batch.query,
        nr_included_samps = DH.nr_included_samps,
        samples = Sample.query,
        NCV_db  = NCV.query,
        NCV_sex = DC.NCV_sex,
        NCV_warnings = DC.NCV_classified)



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
## Wont work.... 
#    chr_abn = ['T13','T18', 'T21', 'X0', 'XXX','XXY','XYY']     
#    for abn in chr_abn:
        #sample.__dict__["comment_"+abn] = request.form["comment_"+abn]
#        sample.__dict__["status_"+abn] = request.form[abn]
#        sample.__dict__["status_change_"+abn] = dt.strftime('%Y/%m/%d %H:%M:%S')

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

@app.route('/NIPT/samples/<sample_id>/')
@login_required
def sample_page( sample_id):
    sample = Sample.query.filter_by(sample_ID = sample_id).first()
    batch_id = sample.batch_id
    batch = Batch.query.filter_by(batch_id = batch_id).first()
    NCV_db = NCV.query.filter(NCV.batch_id == batch_id)
    DC = DataClasifyer()
    DC.handle_NCV(NCV_db)
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
            abn_status_list = ['Verified','False Positive', 'Probable', 'Suspected'],
            sex_abn_colors  = PP.sex_abn_colors,
            sample = sample, 
            NCV_db = NCV.query.filter_by(sample_ID = sample_id).first(), 
            batch_id = batch_id,
            batch_name = batch.batch_name,
            batch = batch,
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
            tris_thresholds = DC.tris_thresholds,
            NCV_sex = DC.NCV_sex[sample_id],
            NCV_warn = DC.NCV_classified[sample_id])

@app.route('/NIPT/batches/<batch_id>/')
@login_required
def sample(batch_id):
    NCV_db = NCV.query.filter(NCV.batch_id == batch_id)
    sample_db = Sample.query.filter(Sample.batch_id == batch_id)
    batch = Batch.query.filter(Batch.batch_id == batch_id).first()
    DC = DataClasifyer()
    DC.handle_NCV(NCV_db)
    DC.get_QC_warnings(sample_db)
    DC.get_manually_classified(sample_db)
    PP = PlottPage(batch_id)
    PP.make_NCV_stat()
    PP.make_chrom_abn()
    PP.make_cov_plot_data()
    return render_template('batch_page.html',
        NCV_samples     = NCV.query.filter(NCV.batch_id == batch_id),
        batch_name      = batch.batch_name,
        man_class       = DC.man_class,
        NCV_stat        = PP.NCV_stat,
        NCV_sex         = DC.NCV_sex,
        seq_date        = batch.date,
        nr_validation_samps = PP.nr_validation_samps,
        samp_range      = range(len(PP.NCV_stat['NCV_X']['NCV_cases'])),
        tris_chrom_abn  = PP.tris_chrom_abn,
        sex_chrom_abn   = PP.sex_chrom_abn,
        abn_status_list = ['Verified','False Positive', 'Probable', 'Suspected'],
        many_colors     = PP.many_colors,
        sex_abn_colors  = PP.sex_abn_colors,
        sex_tresholds   = DC.sex_tresholds,
        tris_thresholds = DC.tris_thresholds,
        seq_warnings = DC.QC_warnings,
        warnings = DC.NCV_classified,
        NCV_rounded = DC.NCV_data,
        samp_cov_db = PP.coverage_plot,
        sample_ids = ','.join(sample.sample_ID for sample in NCV_db))


@app.route('/NIPT/statistics/')
@login_required
def statistics():
    ST = Statistics()
    ST.get_20_latest()
    ST.make_NonExcludedSites2Tags()
    ST.make_GCBias()
    ST.make_Ratio()
    ST.make_NCD_Y()
    ST.make_Tags2IndexedReads()
    ST.make_TotalIndexedReads2Clusters()
    ST.make_Library_nM()
    ST.make_PCS()
    return render_template('statistics.html',
        ticks = range(1,len(ST.NonExcludedSites2Tags)+1),
        NonExcludedSites2Tags = ST.NonExcludedSites2Tags,
        GCBias = ST.GCBias,
        Ratio_13 = ST.Ratio_13,
        Ratio_18 = ST.Ratio_18,
        Ratio_21 = ST.Ratio_21,
        NCD_Y = ST.NCD_Y,
        PCS = ST.PCS,
        thresholds = ST.thresholds,
        Library_nM = ST.Library_nM,
        Tags2IndexedReads = ST.Tags2IndexedReads,
        TotalIndexedReads2Clusters = ST.TotalIndexedReads2Clusters,
        batch_ids = ST.batch_ids,
        batch_names = ST.batch_names,
        dates = ST.dates)
        
