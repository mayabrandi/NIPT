# encoding: utf-8
from database import User, Sample, Batch, Coverage, NCV, BatchStat, db
import logging ### Add logging!!
import os
import csv
import statistics
from datetime import datetime
import ast
import numpy as np


############################################Managing Data####################################################
class DataBaseToCSV:
    """Merges all tables in the tatabase into one csv-file"""
    def __init__(self):
        self.columns = list(set(Sample.query.all()[0].__dict__.keys() + 
                                Coverage.query.all()[0].__dict__.keys() + 
                                NCV.query.all()[0].__dict__.keys() + 
                                BatchStat.query.all()[0].__dict__.keys() + 
                                Batch.query.all()[0].__dict__.keys()))
        self.all_samps = Sample.query.with_entities(Sample.sample_ID)
        self.dict_data = []

    def WriteDictToCSV(self):
        """Transform dicts to csv"""
        csv_file = 'temp.csv'
        csvfile = open(csv_file, 'w')
        writer = csv.DictWriter(csvfile, fieldnames = self.columns)
        writer.writeheader()
        for data in self.dict_data:
            encoded_data = {}
            for key, val in data.items():
                try:
                    val = val.replace(',','.')
                except:
                    pass
                try:
                    encoded_data[key] = val.encode('utf-8')
                except:
                    encoded_data[key] = val
            writer.writerow(encoded_data)
        csvfile = open(csv_file, 'r')
        csvReader = csv.reader(csvfile)
        csvData = list(csvReader)
        csvStrings= []
        for csvLine in csvData:
            csvStrings += [",".join(csvLine)]
        return "\n".join(csvStrings) 
 
    def get_dict_data(self): 
        """Joining all databases into one dict"""
        for s in self.all_samps:
            sample_id = s.sample_ID
            db_dict = db_dict = dict.fromkeys(self.columns, '') 
            samp_dict = Sample.query.filter_by(sample_ID = sample_id).first().__dict__
            ncv_dict = NCV.query.filter_by(sample_ID = sample_id).first().__dict__
            cov_dict = Coverage.query.filter_by(sample_ID = sample_id).first().__dict__
            batch_id = samp_dict['batch_id']
            bs_dict = BatchStat.query.filter_by(batch_id = batch_id).first().__dict__
            btc_dict = Batch.query.filter_by(batch_id = batch_id).first().__dict__
            db_dict.update(samp_dict)
            db_dict.update(ncv_dict)
            db_dict.update(cov_dict)
            db_dict.update(btc_dict)
            db_dict.update(bs_dict)
            self.dict_data.append(db_dict)


class BatchDataFilter():
    """Class to filter out the control samples"""
    def __init__(self):
        self.filtered_NCV = self._fliter_NA()
        self.NCV_passed = self.filtered_NCV.filter(NCV.include)
        self.NCV_passed_X = [float(s.NCV_X) for s in self.NCV_passed.all()]

    def control_NCV13(self):
        control_normal =   self.NCV_passed.join(Sample).filter_by(status_T13 = "Normal")
        control_normal = [float(s.NCV_13) for s in control_normal]
        control_abnormal = self.NCV_passed.join(Sample).filter(Sample.status_T13 !='Normal',
                        Sample.status_T13 !='Failed', Sample.status_T13 !=None).all()
        return control_normal, control_abnormal

    def control_NCV18(self):
        control_normal = self.NCV_passed.join(Sample).filter_by(status_T18 = "Normal")
        control_normal = [float(s.NCV_18) for s in control_normal]
        control_abnormal = self.NCV_passed.join(Sample).filter(Sample.status_T18 !='Normal',
                        Sample.status_T18 !='Failed', Sample.status_T18 !=None).all()
        return control_normal, control_abnormal

    def control_NCV21(self):
        control_normal = self.NCV_passed.join(Sample).filter_by(status_T21 = "Normal")
        control_normal = [float(s.NCV_21) for s in control_normal]
        control_abnormal = self.NCV_passed.join(Sample).filter(Sample.status_T21 !='Normal',
                        Sample.status_T21 !='Failed', Sample.status_T21 !=None).all()
        return control_normal, control_abnormal

    def control_NCVXY(self):
        control_normal = self.NCV_passed.join(Sample).filter_by(status_X0 = "Normal",
                                                                status_XXX = "Normal",
                                                                status_XXY = "Normal",
                                                                status_XYY = "Normal")
        control_normal_X = []
        control_normal_Y = []
        control_normal_XY_names = []
        for s in control_normal:
            control_normal_X.append(float(s.NCV_X))
            control_normal_Y.append(float(s.NCV_Y))
            control_normal_XY_names.append(s.sample_name)

        return control_normal_X, control_normal_Y, control_normal_XY_names 

    def _fliter_NA(self):
        """Filtering out NA. Could probably be done in a more preyyt way :/"""
        return NCV.query.filter(
                NCV.NCV_13!='NA',
                NCV.NCV_18!='NA',
                NCV.NCV_21!='NA',
                NCV.NCV_X!='NA',
                NCV.NCV_Y!='NA')


class DataClasifyer():
    """Contains a bunch of functions for classifying samples in different ways."""
    def __init__(self, NCV_db=None):
        self.NCV_db = NCV_db
        self.NCV_data = {} 
        self.exceptions = ['NA','']
        self.NCV_classified = {}
        self.NCV_sex = {}
        self.sample_names = {}
        self.QC_warnings = {}
        self.NCV_comment = {}
        self.NCV_included = {}
        self.man_class = {}
        self.batch = {}
        self.man_class_merged = {}
        self.sex_tresholds   = {}
        self.ncvy = 20
        self.tris_thresholds = {'soft_max': {'NCV': 3 , 'color': 'orange', 'text' : 'Warning threshold = 3'},
                                'soft_min': {'NCV': -4, 'color': 'orange', 'text' : 'Warning threshold = -4'},
                                'hard_max': {'NCV': 4 , 'color': 'red', 'text' : 'Threshold = 4'},
                                'hard_min': {'NCV': -5, 'color': 'red', 'text' : 'Threshold = -5'} }

    def make_sex_tresholds(self, x_list):
        x_min =  min(x_list) - 1
        if x_min > -40: 
            x_min = -40 
        x_max_upper = 5.05
        x_max_lower = -5.13
        y_min_upper = -15.409 * x_min + 91.417
        y_max_upper = -15.409 * x_max_upper + 91.417
        y_min_lower = -15.256 * x_min - 62.309
        y_max_lower = -15.256 * x_max_lower - 62.309
        self.sex_tresholds = {'XY_horis' :  {'x' : [x_min, 10],         
                                             'y' : [self.ncvy, self.ncvy],
                                            'text' : 'Y='+str(self.ncvy)},
                                'XY_upper': {'x' : [x_min, x_max_upper],
                                             'y' : [y_min_upper, y_max_upper],
                                            'text' : 'Y = -15.3X+91.4'},
                                'XY_lower': {'x' : [x_min, x_max_lower],
                                             'y' : [y_min_lower, y_max_lower],
                                            'text' : 'Y = -15.3X-62.3'},
                                'XXY' :     {'x' : [-4, -4],    
                                             'y' : [155, y_min_upper],
                                            'text' : 'X=-4'},
                                'X0' :      {'x' : [-4, -4],   
                                             'y' : [self.ncvy, -60],
                                             'text' : 'X=-4'},
                                'XXX' :     {'x' : [4, 4],      
                                             'y' : [self.ncvy, -60],
                                             'text' : 'X=4'}}
        for key, val in self.sex_tresholds.items():
            val['text_position'] = [np.mean(val['x']), np.mean(val['y'])]
            self.sex_tresholds[key] = val

    def get_manually_classified(self, sample_db):
        """Get the manually defined sample status"""
        for s in sample_db:
            self.man_class_merged[s.sample_ID] = []
            self.man_class[s.sample_ID] = {}
            for key in ['T13','T18','T21','X0','XXX','XXY','XYY']:
                status = s.__dict__['status_'+key]
                if status!='Normal':
                    self.man_class[s.sample_ID][key] = status
                    self.man_class_merged[s.sample_ID].append(' '.join([status, key]))
                else:
                    self.man_class[s.sample_ID][key] = '-'
            self.man_class_merged[s.sample_ID] = ', '.join(self.man_class_merged[s.sample_ID])       

    def handle_NCV(self): ############ takes time
        """Get automated warnings, based on preset NCV thresholds"""
        for s in self.NCV_db:
            self.sample_names[s.sample_ID] = s.sample_name
            s_id = s.sample_ID
            self.NCV_comment[s_id] = s.comment
            self.NCV_included[s_id] = s.include
            self.batch[s_id] = {'id':s.batch_id ,'name':s.batch.batch_name}
            samp_warn = []
            self.NCV_data[s_id] = {}
            samp_warn = self._get_tris_warn(s, samp_warn)
            samp_warn = self._get_sex_warn(s, samp_warn)
            samp_warn = self._get_FF_warning(s, samp_warn)
            self.NCV_classified[s.sample_ID] = ', '.join(samp_warn)
            
    def _get_FF_warning(self, s, samp_warn):
        self.NCV_data[s.sample_ID]['FF_Formatted'] = {}
        try:
            FetalFraction = float(s.sample.FF_Formatted.rstrip('%').lstrip('<'))
        except:
            FetalFraction = None
        if FetalFraction:
            self.NCV_data[s.sample_ID]['FF_Formatted']['val'] = FetalFraction
            if FetalFraction < 2:
                samp_warn.append('FF')
                self.NCV_data[s.sample_ID]['FF_Formatted']['warn'] = "danger"
            else:
                self.NCV_data[s.sample_ID]['FF_Formatted']['warn'] = "default"
        return samp_warn

    def _get_sex_warn(self,s, samp_warn):
        """Get automated sex warnings, based on preset NCV thresholds"""
        sex_warn = ''
        if not set([s.NCV_X , s.NCV_Y]).issubset(self.exceptions):
            x = float(s.NCV_X)
            y = float(s.NCV_Y)
            f_h = -15.409*x + 91.417 - y
            f_l = -15.256*x - 62.309 - y
            if 0>=f_h and x<=-4:
                sex_warn = 'XYY'
            elif 0>=f_h and x>=-4 and y>self.ncvy:
                sex_warn = 'XXY'
            elif y<self.ncvy and x>=4:
                sex_warn = 'XXX'
            elif f_l<0<=f_h and y>self.ncvy:
                sex_warn = 'XY'
            elif f_l>0 and x< -4:
                sex_warn = 'X0'
            elif -4<=x<=4 and y<self.ncvy:
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
            if 20<=y<50:
                samp_warn.append(' Compare NCVY with ff!')
                self.NCV_data[s.sample_ID]['NCV_Y']['warn'] = "danger"        
        return samp_warn
  
    def _get_tris_warn(self, s, samp_warn):
        """Get automated trisomi warnings, based on preset NCV thresholds"""
        for key in ['13','18','21','X','Y']:
            if s.__dict__['NCV_'+key] in self.exceptions:
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
        return samp_warn

    def get_QC_warnings(self, samples):  ####### takes Time --
        for sample in samples:
            if (not sample.NonExcludedSites) or (int(sample.NonExcludedSites) < 8000000) or sample.QCFailure or sample.QCWarning:
                self.QC_warnings[sample.sample_ID] = {'sample_ID' : sample, 'missing_data' : '', 'QC_warn' : '', 'QC_fail' : ''}
            if not sample.NonExcludedSites:
                self.QC_warnings[sample.sample_ID]['missing_data'] = 'No data'
            elif int(sample.NonExcludedSites) < 8000000:  
                self.QC_warnings[sample.sample_ID]['missing_data'] = 'Less than 8M reads'
            if sample.QCFailure:
                self.QC_warnings[sample.sample_ID]['QC_fail'] = sample.QCFailure
            if sample.QCWarning:
                self.QC_warnings[sample.sample_ID]['QC_warn'] = sample.QCWarning


###########################################PLOTS#####################################################
class Layout():
    def __init__(self, batch_id=None):
        self.case_size = 11
        self.case_line = 1
        self.abn_size = 7
        self.abn_line = 2
        self.abn_symbol = 'circle-open'
        self.ncv_abn_colors  = {"Suspected"    :   '#DBA901',
                                     'Probable'     :   "#0000FF",
                                     'False Negative':  "#ff6699",
                                     'Verified'     :   "#00CC00",
                                     'Other'        :   "#603116",
                                     "False Positive":  "#E74C3C"}
        self.many_colors = list(['#000000', '#4682B4', '#FFB6C1', '#FFA500', '#FF0000',
                                        '#00FF00', '#0000FF', '#FFFF00', '#00FFFF', '#FF00FF',
                                        '#C0C0C0', '#808080', '#800000', '#808000', '#008000',
                                        '#800080', '#008080', '#000080', '#0b7b47','#7b0b3f','#7478fc'])
        #self.cov_colors = [[i]*22 for i in self.many_colors]
        self.abn_status_X = {'Probable':0,'Verified':0.1,'False Positive':0.2,'False Negative':0.3, 'Suspected':0.4, 'Other': 0.5}
        if batch_id:
            samples = Sample.query.filter(Sample.batch_id == batch_id)                                        
            self.many_colors_dict = {s.sample_ID:self.many_colors[i] for i, s in enumerate(samples)}  
            self.cov_colors = {s.sample_ID: [self.many_colors[i]]*22 for i, s in enumerate(samples)} 

class CoveragePlot():
    """Class to preppare data for the coverage plot"""
    def __init__(self, batch_id):
        self.batch_id = batch_id
        self.cov = Coverage.query.filter(Coverage.batch_id == self.batch_id)
        self.coverage_plot = {'samples':[],'x_axis': range(1,23)}
        self.sample_list = []

    def make_cov_plot_data(self):
        """Preparing coverage plot data"""
        for samp in self.cov:
            samp_cov = []
            for i in self.coverage_plot['x_axis']:
                try:
                    samp_cov.append(float(samp.__dict__['Chr'+str(i)+'_Coverage']))
                except:
                    pass
            self.sample_list.append(samp.sample_ID)
            self.coverage_plot['samples'].append((samp.sample_ID, {'cov':samp_cov, 'samp_id':[samp.sample.sample_name]}))
        self.coverage_plot['samples'].sort()

class SexAbnormality():
    """Class to preppare data for XY - NCV plots 
    (both for batch lavel and sample level)"""
    def __init__(self, batch_id, cases):
        self.batch_id = batch_id
        self.cases = cases
        self.case_data = {'NCV_X':{}, 'NCV_Y' : {}}
        self.abn_status_X = {'Probable':0,'Verified':0.1,'False Positive':0.2,'False Negative':0.3, 'Suspected':0.4, 'Other': 0.5}
        self.sex_chrom_abn = {'X0':{}, 'XXX':{}, 'XXY':{},'XYY':{}}
        self.sample_list = []

    def make_case_data(self, chrom, control_normal):
        """Preparing case data"""
        samples = {}
        sample_list = []
        for s in self.cases:
            try:
                samples[s.sample_ID]={
                "NCV_val" : round(float(s.__dict__[chrom]),2),
                "X_labels" : s.sample_name}
                sample_list.append(s.sample_ID)
            except:
                pass
        
        sample_list.sort()
        self.sample_list = sample_list

        self.case_data[chrom] = {
            'nr_pass' : len(control_normal),
            'samples' : samples,
            'nr_cases' :len(samples),
            'x_axis' : range(2, len(samples)+2),
            'x_range' : [-1, len(samples)+3],
            'chrom' : chrom,
            'NCV_pass' : control_normal}

    def make_sex_chrom_abn(self): 
        """Preparing sex abnormality control samples"""
        for abn in self.sex_chrom_abn.keys():
            for status in self.abn_status_X.keys():
                self.sex_chrom_abn[abn][status] = {'NCV_X' : [], 'NCV_Y' : [], 's_name' : [], 'nr_cases':0}
                cases = Sample.query.filter(Sample.__dict__['status_'+abn] == status)
                for s in cases:
                    NCV_db = NCV.query.filter_by(sample_ID = s.sample_ID).first()
                    if NCV_db.include and (NCV_db.NCV_X!='NA') and NCV_db.NCV_Y!='NA':
                        self.sex_chrom_abn[abn][status]['NCV_X'].append(float(NCV_db.NCV_X))
                        self.sex_chrom_abn[abn][status]['NCV_Y'].append(float(NCV_db.NCV_Y))
                        self.sex_chrom_abn[abn][status]['s_name'].append(s.sample_name)
                        self.sex_chrom_abn[abn][status]['nr_cases']+=1


class TrisAbnormality():
    """Class to preppare data for tris - NCV plots 
    (both for batch lavel and sample level)"""
    def __init__(self,batch_id, cases):
        self.cases = cases
        self.abn_status_X = {'Probable':0,'Verified':0.1,'False Positive':0.2,'False Negative':0.3, 'Suspected':0.4, 'Other': 0.5}
        self.tris_abn = {} # This anoying dict is only for the sample_tris_plot, to make possible for one legend per abnormality
        for status in self.abn_status_X.keys():
            self.tris_abn[status] = {'NCV' : [], 's_name' : [], 'x_axis': [], 'chrom':{'13':0,'18':0,'21':0}}
        self.tris_thresholds = {}
    
    def make_case_data(self, control_normal, chrom):
        """Preparing case data"""
        NCV_cases = []
        X_labels = []
        case_data = {}
        for s in self.cases:
            try:
                NCV_val = round(float(s.__dict__['NCV_'+chrom]),2)
                NCV_cases.append(NCV_val)
                X_labels.append(s.sample_name)
            except:
                pass
        case_data = {
            'nr_pass' : len(control_normal),
            'NCV_cases' : NCV_cases,
            'nr_cases' :len(NCV_cases),
            'x_axis' : range(2, len(NCV_cases)+2),
            'x_range' : [-1, len(NCV_cases)+3],
            'X_labels' : X_labels,
            'chrom' : chrom,
            'NCV_pass' : control_normal}
        return case_data

    def make_tris_chrom_abn(self, abnorm_samples, chrom):
        """Preparing trisomi control samples"""
        tris_chrom_abn = {}
        for status in self.abn_status_X.keys():
            if not status in tris_chrom_abn:
                tris_chrom_abn[status] = {'NCV' : [], 's_name' : [], 'x_axis': [], 'nr': 0}
        for sample in abnorm_samples:
            sample_name = sample.sample_name
            status = sample.sample.__dict__['status_T' + chrom]
            NCV_val = sample.__dict__['NCV_' + chrom]
            if NCV_val!= 'NA' and status in tris_chrom_abn.keys():
                tris_chrom_abn[status]['NCV'].append(float(NCV_val))
                tris_chrom_abn[status]['s_name'].append(sample_name)
                tris_chrom_abn[status]['x_axis'].append(self.abn_status_X[status]-0.2)
                tris_chrom_abn[status]['nr']+=1  
        return tris_chrom_abn
    
    def make_tris_abn_sample_page(self, abnorm_samples):
        """Preparing trisomi control samples for sample page"""
        base_x = {'13':1,'18':2,'21':3}
        for chrom in base_x.keys():
            for sample in abnorm_samples:
                sample_name = sample.sample_name
                status = sample.sample.__dict__['status_T' + chrom]
                NCV_val = sample.__dict__['NCV_' + chrom]
                if NCV_val!= 'NA' and status in self.tris_abn.keys():
                    self.tris_abn[status]['NCV'].append(float(NCV_val))
                    self.tris_abn[status]['s_name'].append(sample_name)
                    self.tris_abn[status]['x_axis'].append(base_x[chrom] + self.abn_status_X[status] - 0.25)
                    self.tris_abn[status]['chrom'][chrom]+=1


class FetalFraction():
    """Class to prepare Fetal Fraction Plot"""
    def __init__(self,batch_id):
        self.dbNCV = NCV.query.filter(NCV.batch_id == batch_id, NCV.NCV_Y!='NA',NCV.NCV_X!='NA').all()
        self.dbSample = Sample.query.filter(Sample.batch_id == batch_id, Sample.FF_Formatted!='NA').all()
        self.samples = {}
        self.sample_list = []
        self.control = {'NCV_X':[],'NCV_Y':[],'FF':[]}
        self.perdiction = {'NCV_X':{},'NCV_Y':{}}
        self.nr_contol_samples = None

    def form_prediction_interval(self):

        #y=0.0545x + 5.9299
        self.perdiction['NCV_Y']['max'] = {'x':[0,500],'y':[5.9299,33.1799]}

        #y=0.0545x - 3.3899
        self.perdiction['NCV_Y']['min'] = {'x':[0,500],'y':[-3.3899,23.8601]}

        self.perdiction['NCV_Y']['ff_min'] = {'x':[0, 500],'y':[2, 2]}
        self.perdiction['NCV_Y']['NCV_Y_min'] = {'x':[20, 20],'y':[0, 35]}

        #y=-0.8074x + 7.861
        self.perdiction['NCV_X']['min'] = {'x':[-30,5],'y':[32.083,3.824]}

        #y=-0.8062x - 3.2337
        self.perdiction['NCV_X']['max'] = {'x':[-30,5],'y':[20.9523,-7.2647]}

        self.perdiction['NCV_X']['ff_min'] = {'x':[-30,5],'y':[2, 2]}

    def format_case_dict(self):
        for samp in self.dbSample:
            self.samples[samp.sample_ID] = {}
            self.samples[samp.sample_ID]['FF'] = int(samp.FF_Formatted.rstrip('%'))
        for samp in self.dbNCV:
            if not samp.sample_ID in self.samples:
               self.samples[samp.sample_ID] = {} 
            self.samples[samp.sample_ID]['name'] = samp.sample_name
            self.samples[samp.sample_ID]['NCVY'] = float(samp.NCV_Y)
            self.samples[samp.sample_ID]['NCVX'] = float(samp.NCV_X)
        self.sample_list = self.samples.keys()
        self.sample_list.sort()

    def format_contol_dict(self):
        FF_normal = Sample.query.filter(Sample.FF_Formatted!=None,
                                        Sample.status_X0 == "Normal",
                                        Sample.status_XXX == "Normal",
                                        Sample.status_XXY == "Normal",
                                        Sample.status_XYY == "Normal")
        FF_normal=FF_normal.join(NCV).filter(NCV.NCV_X!='NA', NCV.NCV_Y!='NA',NCV.include==True).all()
        NCV_normal = NCV.query.filter(NCV.NCV_X!='NA', NCV.NCV_Y!='NA',NCV.include==True)
        NCV_normal=NCV_normal.join(Sample).filter(Sample.FF_Formatted!='NA',
                                        Sample.status_X0 == "Normal",
                                        Sample.status_XXX == "Normal",
                                        Sample.status_XXY == "Normal",
                                        Sample.status_XYY == "Normal").all()

        for sample in FF_normal:
            self.control['FF'].append(int(sample.FF_Formatted.rstrip('%')))

        for sample in NCV_normal:
            self.control['NCV_X'].append(float(sample.NCV_X))
            self.control['NCV_Y'].append(float(sample.NCV_Y))

        self.nr_contol_samples = len(self.control['FF'])


class CovXCovY():
    """Class to prepare CovX vs CovY Plot"""
    def __init__(self,batch_id):
        self.pos_contol = {'X0':{}, 'XXX':{}, 'XXY':{},'XYY':{}} 
        self.batch_id = batch_id
        self.samples = {}
        self.sample_list = []
        self.control = {'CovY':[],'CovX':[]}
        self.nr_contol_samples = None
        self.coverage_query = Coverage.query.filter(Coverage.ChrX_Coverage != 'NA', Coverage.ChrX_Coverage!='NA')
        
    def format_case_dict(self):
        dbCoverage = Coverage.query.filter(Coverage.batch_id == self.batch_id).all()
        for samp in dbCoverage:
            self.samples[samp.sample_ID] = {'CovY' : float(samp.ChrY_Coverage),
                                            'CovX' : float(samp.ChrX_Coverage),
                                            'name' : samp.sample.sample_name}
        self.sample_list = self.samples.keys()
        self.sample_list.sort()

    def format_contol_dict(self):
        XY_normal = self.coverage_query.join(Sample).filter(Sample.status_X0 == "Normal",
                                        Sample.status_XXX == "Normal",
                                        Sample.status_XXY == "Normal",
                                        Sample.status_XYY == "Normal")
        XY_normal = XY_normal.join(NCV).filter(NCV.include==True).all()

        for sample in XY_normal:
            self.control['CovX'].append(float(sample.ChrX_Coverage))
            self.control['CovY'].append(float(sample.ChrY_Coverage))

        self.nr_contol_samples = len(self.control['CovY'])

    def format_pos_contol(self): 
        """Preparing sex aabnormality control samples"""
        for abn in self.pos_contol:
            for status in Layout().abn_status_X.keys():
                self.pos_contol[abn][status] = {'CovX' : [], 'CovY' : [], 's_name' : []}
                pos_controls = self.coverage_query.join(Sample).filter(Sample.__dict__['status_'+abn] == status)
                pos_controls = pos_controls.join(NCV).filter(NCV.include==True).all()
                for sample in pos_controls:
                    self.pos_contol[abn][status]['CovX'].append(float(sample.ChrX_Coverage))
                    self.pos_contol[abn][status]['CovY'].append(float(sample.ChrY_Coverage))
                    self.pos_contol[abn][status]['s_name'].append(sample.sample_ID)


class Statistics():
    """Class to preppare data for statistics plots"""
    def __init__(self):
        self.batches = Batch.query.all()
        self.NonExcludedSites2Tags={}
        self.TotalIndexedReads2Clusters = {}
        self.Tags2IndexedReads = {}
        self.GCBias = {}
        self.Library_nM = {}
        self.batch_ids = []
        self.dates = []
        self.batch_names = []
        self.Ratio_13 = {}
        self.Ratio_18 = {}
        self.Ratio_21 = {}
        self.Stdev_13 = {}
        self.Stdev_18 = {}
        self.Stdev_21 = {}
        self.NCD_Y = {}
        self.PCS = {}
        self.FF_Formatted = {}
        self.Clusters = {}
        self.NonExcludedSites = {}
        self.PerfectMatchTags2Tags = {}
        self.thresholds = {
            'GCBias': {'upper': 0.5, 'lower': -0.5}, #
            'NonExcludedSites2Tags': {'upper':1, 'lower':0.8}, #
            'Tags2IndexedReads': {'upper':0.9, 'lower':0.75}, # 
            'TotalIndexedReads2Clusters': {'upper':1, 'lower':0.7},#
            'Library_nM': {'upper':150, 'lower':10, 'wished':40},
            'Ratio_13': {'upper':0.2012977, 'lower':0.1996}, ##
            'Ratio_18': {'upper':0.2517526, 'lower':0.2495}, ##
            'Ratio_21': {'upper':0.2524342, 'lower':0.2492}, ##
            'NCD_Y': {'lower' : 80, 'lower_nr2' : -100, 'upper': 1000}, ##
            'FF_Formatted': {'lower':2},
            'Stdev_13' : {'upper' : 0.000673, 'lower' : 0},
            'Stdev_18' : {'upper' : 0.00137, 'lower' : 0},
            'Stdev_21' : {'upper' : 0.00133, 'lower' : 0},
            'Clusters' : {'upper' : 450000000, 'lower' : 250000000},
            'NonExcludedSites' : {'upper' : 100000000, 'lower' : 8000000},
            'PerfectMatchTags2Tags' : {'upper' : 1, 'lower' : 0.7},
            }           

    def get_20_latest(self):
        all_batches = []
        for batch in self.batches:
            all_batches.append((batch.date, batch))
        last_40 = sorted(all_batches, reverse=True)[0:40]
        last_20 = sorted(last_40)
        for date, batch in last_20:
            self.batch_ids.append(batch.batch_id)        
            self.dates.append(date)
            self.batch_names.append(batch.batch_name)

    def make_statistics_from_database_Sample(self):
        i=1
        for batch_id in self.batch_ids:
            self.Library_nM[batch_id]={'x':[],'y':[]}
            self.NonExcludedSites2Tags[batch_id]={'x':[],'y':[]}
            self.GCBias[batch_id]={'x':[],'y':[]}
            self.Tags2IndexedReads[batch_id]={'x':[],'y':[]}
            self.FF_Formatted[batch_id]={'x':[],'y':[]}
            self.TotalIndexedReads2Clusters[batch_id]={'x':[],'y':[]}
            self.Clusters[batch_id] = {'x':[], 'y':[]}
            self.NonExcludedSites[batch_id] = {'x':[], 'y':[]}
            self.PerfectMatchTags2Tags[batch_id] = {'x':[], 'y':[]}
            samps = Sample.query.filter(Sample.batch_id==batch_id)
            for samp in samps:
                FF = samp.FF_Formatted.rstrip('%').lstrip('<')
                try:
                    self.FF_Formatted[batch_id]['y'].append(float(FF))
                    self.FF_Formatted[batch_id]['x'].append(i)
                except:
                    logging.exception('Failed to read FF')
                    pass
                try:
                    self.Library_nM[batch_id]['y'].append(float(samp.Library_nM))
                    self.Library_nM[batch_id]['x'].append(i)
                except:
                    logging.exception('')
                    pass
                try:
                    self.NonExcludedSites2Tags[batch_id]['y'].append(float(samp.NonExcludedSites2Tags))
                    self.NonExcludedSites2Tags[batch_id]['x'].append(i)
                except:
                    logging.exception('')
                    pass
                try:
                    self.GCBias[batch_id]['y'].append(float(samp.GCBias))
                    self.GCBias[batch_id]['x'].append(i)
                except:
                    logging.exception('')
                    pass
                try:
                    self.Tags2IndexedReads[batch_id]['y'].append(float(samp.Tags2IndexedReads))
                    self.Tags2IndexedReads[batch_id]['x'].append(i)
                except:
                    logging.exception('')
                    pass
                try:
                    self.TotalIndexedReads2Clusters[batch_id]['y'].append(float(samp.TotalIndexedReads2Clusters))
                    self.TotalIndexedReads2Clusters[batch_id]['x'].append(i)
                except:
                    logging.exception('')
                    pass
                try:
                    self.Clusters[batch_id]['y'].append(float(samp.Clusters))
                    self.Clusters[batch_id]['x'].append(i)
                except:
                    logging.exception('')
                    pass
                try:
                    self.NonExcludedSites[batch_id]['y'].append(float(samp.NonExcludedSites))
                    self.NonExcludedSites[batch_id]['x'].append(i)
                except:
                    logging.exception('')
                    pass
                try:
                    self.PerfectMatchTags2Tags[batch_id]['y'].append(float(samp.PerfectMatchTags2Tags))
                    self.PerfectMatchTags2Tags[batch_id]['x'].append(i)
                except:
                    logging.exception('')
                    pass
            i+=1

    def make_Stdev(self):
        i=1
        for batch_id in self.batch_ids:
            self.Stdev_13[batch_id]={'x':[],'y':[]}
            self.Stdev_18[batch_id]={'x':[],'y':[]}
            self.Stdev_21[batch_id]={'x':[],'y':[]}
            batch_stat = BatchStat.query.filter(BatchStat.batch_id==batch_id)
            for samp in batch_stat: ##should always be only one
                try:
                    self.Stdev_13[batch_id]['y'].append(float(samp.Stdev_13))
                    self.Stdev_13[batch_id]['x'].append(i)
                    self.Stdev_18[batch_id]['y'].append(float(samp.Stdev_18))
                    self.Stdev_18[batch_id]['x'].append(i)
                    self.Stdev_21[batch_id]['y'].append(float(samp.Stdev_21))
                    self.Stdev_21[batch_id]['x'].append(i)
                except:
                    logging.exception('')
                    pass
            i+=1

    def make_PCS(self):
        i=1
        PCS_all = {}
        for batch_id in self.batch_ids:
            samps = NCV.query.filter(NCV.batch_id==batch_id)
            self.PCS[batch_id] = {} 
            for samp in samps:
                if samp.sample_ID.split('-')[0].lower()=='pcs':
                    pcs_id = samp.sample_ID.split('_')[0].lower()
                    if not pcs_id in PCS_all.keys():
                        PCS_all[pcs_id] = {'values' : [], 'ticks' : [], 'tresholds' : {}}
                    try:
                        PCS_all[pcs_id]['values'].append(float(samp.NCV_X))
                        PCS_all[pcs_id]['ticks'].append(i)
                    except:
                        logging.exception('')
                        pass
                    try:
                        self.PCS[batch_id][samp.sample_ID] = {'x':[],'y':[],'sample':[]}
                        self.PCS[batch_id][samp.sample_ID]['y'].append(float(samp.NCV_X))
                        self.PCS[batch_id][samp.sample_ID]['x'].append(i)
                        self.PCS[batch_id][samp.sample_ID]['sample'] = samp.sample_ID
                    except:
                        logging.exception('')
                        pass
            i+=1
        for pcs in PCS_all:
            med = float(statistics.median(PCS_all[pcs]['values']))
            PCS_all[pcs]['tresholds']['lower'] = [med - 1.45]*len(PCS_all[pcs]['ticks'])
            PCS_all[pcs]['tresholds']['upper'] = [med + 1.45]*len(PCS_all[pcs]['ticks'])
        self.thresholds['PCS'] = PCS_all

    def make_statistics_from_database_NCV(self):
        i=1
        for batch_id in self.batch_ids:
            self.Ratio_13[batch_id] = {'x':[],'y':[]}
            self.Ratio_18[batch_id] = {'x':[],'y':[]}
            self.Ratio_21[batch_id] = {'x':[],'y':[]}
            self.NCD_Y[batch_id] = {'x':[],'y':[]}
            samps = NCV.query.filter(NCV.batch_id==batch_id)
            for samp in samps:
                try:
                    self.Ratio_13[batch_id]['y'].append(float(samp.Ratio_13))
                    self.Ratio_13[batch_id]['x'].append(i)
                    self.Ratio_18[batch_id]['y'].append(float(samp.Ratio_18))
                    self.Ratio_18[batch_id]['x'].append(i)
                    self.Ratio_21[batch_id]['y'].append(float(samp.Ratio_21))
                    self.Ratio_21[batch_id]['x'].append(i)
                except Exception as e:
                    logging.exception(e)
                    pass
                try:
                    self.NCD_Y[batch_id]['y'].append(float(samp.NCD_Y))
                    self.NCD_Y[batch_id]['x'].append(i)
                except:
                    logging.exception('')
            i+=1

