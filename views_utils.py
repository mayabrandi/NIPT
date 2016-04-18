# encoding: utf-8
from database import User, Sample, Batch, Coverage, NCV, BatchStat, db
import logging ### Add logging!!
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
        self.NCV_classified = {}
        self.NCV_sex = {}
        self.QC_warnings = {}
        self.man_class = {}
        self.sex_tresholds = {'XY_horis' :  {'x' : [-40, 10],   'y' : [13, 13]},
                                'XY_upper': {'x' : [-40, 5.05], 'y' : [707.777, 13.6016]},#-30,553.687
                                'XY_lower': {'x' : [-40, -5.13],'y' : [551.659, 13.971]}, #-30,395.371
                                'XXY' :     {'x' : [-4, -4],    'y' : [155, 700]},
                                'X0' :      {'x' : [-4, -4],   'y' : [13, -40]},
                                'XXX' :     {'x' : [4, 4],      'y' : [13, -40]}}
        self.tris_thresholds = {'soft_max': {'NCV': 3 , 'color': 'orange'},
                                'soft_min': {'NCV': -4, 'color': 'orange'},
                                'hard_max': {'NCV': 4 , 'color': 'red'},
                                'hard_min': {'NCV': -5, 'color': 'red'} }

    def get_manually_classified(self, sample_db):
        for s in sample_db:
            self.man_class[s.sample_ID] = []
            for key in ['T13','T18','T21','X0','XXX','XXY','XYY']:  
                status = s.__dict__['status_'+key]
                if status!='Normal':
                    self.man_class[s.sample_ID].append(' '.join([status, key]))
            self.man_class[s.sample_ID] = ', '.join(self.man_class[s.sample_ID])       

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
                elif f_l<0<=f_h and y>13:
                    sex_warn = 'XY'
                elif f_l>0 and x< -4:
                    sex_warn = 'X0'
                elif -4<=x<=4 and y<13:
                    sex_warn = 'XX'
            if sex_warn in ['XX','XY']:
                self.NCV_data[s.sample_ID]['NCV_Y']['warn'] = "default"
                self.NCV_data[s.sample_ID]['NCV_X']['warn'] = "default"  
                sex = sex_warn              
            elif sex_warn:
                self.NCV_data[s.sample_ID]['NCV_Y']['warn'] = "danger"
                self.NCV_data[s.sample_ID]['NCV_X']['warn'] = "danger"
                samp_warn.append(sex_warn)
                sex = 'ambiguous'
            else:
                self.NCV_data[s.sample_ID]['NCV_Y']['warn'] = "default"
                self.NCV_data[s.sample_ID]['NCV_X']['warn'] = "default"
                sex = 'ambiguous'
            self.NCV_sex[s.sample_ID] = sex
            self.NCV_classified[s.sample_ID] = ', '.join(samp_warn)

    def get_QC_warnings(self, samples):
#        low_NES = self.BDH.samples_on_batch.filter(Sample.NonExcludedSites < 8000000)
        QC_flagged = samples.filter(Sample.QCFlag > 0)
        ##QC_flagged = self.BDH.samples_on_batch.filter(Sample.QCFlag > 0)
#        for sample in set(self.NCV_classified.keys() + [sample.sample_ID for sample in low_NES] + [sample.sample_ID for sample in QC_flagged]):
#            self.QC_warnings[sample] = {'sample_ID' : sample, 'missing_data' : '', 'QC_warn' : '', 'QC_fail' : '', 'NCV_low': ''}
#        for sample in set(self.NCV_classified.keys() + [sample.sample_ID for sample in QC_flagged]):
        for sample in set([sample.sample_ID for sample in QC_flagged]):
            self.QC_warnings[sample] = {'sample_ID' : sample, 'QC_warn' : '', 'QC_fail' : ''}
       # for sample_id, warning in self.NCV_classified.items():
         #   self.QC_warnings[sample_id]['NCV_high'] = warning
#        for sample in low_NES:
#            self.QC_warnings[sample.sample_ID]['missing_data'] = 'warning: lt 8M reads'
        for sample in QC_flagged:
            self.QC_warnings[sample.sample_ID]['QC_fail'] = sample.QCFailure if sample.QCFailure else ''
            self.QC_warnings[sample.sample_ID]['QC_warn'] = sample.QCWarning if sample.QCWarning else ''



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
        status_x = {'Probable':0.1,'Verified':0.2,'False Positive':0.3,'False Negative':0.4, 'Suspected':0.5}
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





class Statistics():
    """Class to preppare data for NCV plots"""
    def __init__(self):
        self.batches = Batch.query.all()
        self.NonExcludedSites2Tags={}
        self.TotalIndexedReads2Clusters = {}
        self.Tags2IndexedReads = {}
        self.GCBias = {}
        self.Library_nM = {}
        self.batch_ids = []
        self.dates = []
        self.batch_names = {}
        self.Ratio_13 = {}
        self.Ratio_18 = {}
        self.Ratio_21 = {}
        self.NCD_Y = {}

    def get_20_latest(self):
        all_batches = {}
        for batch in self.batches:
            all_batches[batch.date] = batch
        last_20 = sorted(all_batches.items(), reverse=True)[0:20]   
        last_20 = sorted(last_20)
        for date, batch in last_20:
            self.batch_ids.append(batch.batch_id)        
            self.dates.append(date)
            self.batch_names[batch.batch_id] = batch.batch_name
 
    def make_Library_nM(self):
        i=1
        for batch_id in self.batch_ids:
            self.Library_nM[batch_id]={'x':[],'y':[]}
            samps = Sample.query.filter(Sample.batch_id==batch_id)
            for samp in samps:
                try:                    
                    self.Library_nM[batch_id]['y'].append(float(samp.Library_nM))
                    self.Library_nM[batch_id]['x'].append(i)
                except:
                    pass
            i+=1

    def make_NonExcludedSites2Tags(self):
        i=1
        for batch_id in self.batch_ids:
            self.NonExcludedSites2Tags[batch_id]={'x':[],'y':[]}
            samps = Sample.query.filter(Sample.batch_id==batch_id)
            for samp in samps:
                try:
                    self.NonExcludedSites2Tags[batch_id]['y'].append(float(samp.NonExcludedSites2Tags))
                    self.NonExcludedSites2Tags[batch_id]['x'].append(i)
                except:
                    pass
            i+=1

    def make_GCBias(self):
        i=1
        for batch_id in self.batch_ids:
            self.GCBias[batch_id]={'x':[],'y':[]}
            samps = Sample.query.filter(Sample.batch_id==batch_id)
            for samp in samps:
                try:
                    self.GCBias[batch_id]['y'].append(float(samp.GCBias))
                    self.GCBias[batch_id]['x'].append(i)
                except:
                    pass
            i+=1

    def make_Tags2IndexedReads(self):
        i=1
        for batch_id in self.batch_ids:
            self.Tags2IndexedReads[batch_id]={'x':[],'y':[]}
            samps = Sample.query.filter(Sample.batch_id==batch_id)
            for samp in samps:
                try:
                    self.Tags2IndexedReads[batch_id]['y'].append(float(samp.Tags2IndexedReads))
                    self.Tags2IndexedReads[batch_id]['x'].append(i)
                except:
                    pass
            i+=1

    def make_TotalIndexedReads2Clusters(self):
        i=1
        for batch_id in self.batch_ids:
            self.TotalIndexedReads2Clusters[batch_id]={'x':[],'y':[]}
            samps = Sample.query.filter(Sample.batch_id==batch_id)
            for samp in samps:
                try:
                    self.TotalIndexedReads2Clusters[batch_id]['y'].append(float(samp.TotalIndexedReads2Clusters))
                    self.TotalIndexedReads2Clusters[batch_id]['x'].append(i)
                except:
                    pass
            i+=1

    def make_Ratio(self):
        i=1
        for batch_id in self.batch_ids:
            self.Ratio_13[batch_id]={'x':[],'y':[]}
            self.Ratio_18[batch_id]={'x':[],'y':[]}
            self.Ratio_21[batch_id]={'x':[],'y':[]}
            samps = NCV.query.filter(NCV.batch_id==batch_id)
            for samp in samps:
                try:
                    self.Ratio_13[batch_id]['y'].append(float(samp.Ratio_13))
                    self.Ratio_13[batch_id]['x'].append(i)
                    self.Ratio_18[batch_id]['y'].append(float(samp.Ratio_18))
                    self.Ratio_18[batch_id]['x'].append(i)
                    self.Ratio_21[batch_id]['y'].append(float(samp.Ratio_21))
                    self.Ratio_21[batch_id]['x'].append(i)
                except:
                    pass
            i+=1

    def make_NCD_Y(self):
        i=1
        for batch_id in self.batch_ids:
            self.NCD_Y[batch_id]={'x':[],'y':[]}
            self.NCD_Y[batch_id]={'x':[],'y':[]}
            self.NCD_Y[batch_id]={'x':[],'y':[]}
            samps = NCV.query.filter(NCV.batch_id==batch_id)
            for samp in samps:
                try:
                    self.NCD_Y[batch_id]['y'].append(float(samp.NCD_Y))
                    self.NCD_Y[batch_id]['x'].append(i)
                except:
                    pass
            i+=1
