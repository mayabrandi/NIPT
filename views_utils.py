# encoding: utf-8
from database import User, Sample, Batch, Coverage, NCV, BatchStat, db
import logging ### Add logging!!
import os
import csv
import statistics
from datetime import datetime
import ast
import numpy as np


################################################################################################

class DataBaseToCSV:
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

################################################################################################

class BatchDataFilter():
    def __init__(self):
        self.filtered_NCV = self.fliter_NA()
        self.NCV_passed = self.filtered_NCV.filter(NCV.include)
        self.NCV_passed_X = [float(s.NCV_X) for s in self.NCV_passed.all()]
        self.NCV_normal = {'NCV_13' : self.NCV_passed.join(Sample).filter_by(status_T13 = "Normal"),
                           'NCV_18' : self.NCV_passed.join(Sample).filter_by(status_T18 = "Normal"),
                           'NCV_21' : self.NCV_passed.join(Sample).filter_by(status_T21 = "Normal"),
                           'NCV_XY' : self.NCV_passed.join(Sample).filter_by(status_X0 = "Normal", 
                                    status_XXX = "Normal", status_XXY = "Normal", 
                                    status_XYY = "Normal")}

    def batch_data(self, batch_id):
        return self.filtered_NCV.filter(NCV.batch_id == batch_id,
                                            NCV.sample_ID.notilike('%ref%'),
                                            NCV.sample_ID.notilike('%Control%'))


    def fliter_NA(self):
        """Filtering out NA. Could probably be done in a more preyyt way :/"""
        return NCV.query.filter(
                NCV.NCV_13!='NA',
                NCV.NCV_18!='NA',
                NCV.NCV_21!='NA',
                NCV.NCV_X!='NA',
                NCV.NCV_Y!='NA')

################################################################################################


class DataClasifyer():
    def __init__(self, NCV_db):
        self.NCV_db = NCV_db
        self.NCV_data = {} 
        self.NCV_names = ['13','18','21','X','Y']
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
                                             'y' : [13, 13],
                                            'text' : 'NCV=13'},
                                'XY_upper': {'x' : [x_min, x_max_upper],
                                             'y' : [y_min_upper, y_max_upper],
                                            'text' : ''},
                                'XY_lower': {'x' : [x_min, x_max_lower],
                                             'y' : [y_min_lower, y_max_lower],
                                            'text' : ''},
                                'XXY' :     {'x' : [-4, -4],    
                                             'y' : [155, y_min_upper],
                                            'text' : ''},
                                'X0' :      {'x' : [-4, -4],   
                                             'y' : [13, -60],
                                             'text' : 'NCV=-4'},
                                'XXX' :     {'x' : [4, 4],      
                                             'y' : [13, -60],
                                             'text' : 'NCV=4'}}
        for key, val in self.sex_tresholds.items():
            val['text_position'] = [val['x'][1], val['y'][1]-15]
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
        try:
            FetalFraction = int(s.sample.FF_Formatted.rstrip('%').lstrip('<'))
        except:
            FetalFraction = None
        if FetalFraction and FetalFraction < 2:
            samp_warn.append('FF')
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
        return samp_warn

    def _get_tris_warn(self, s, samp_warn):
        """Get automated trisomi warnings, based on preset NCV thresholds"""
        for key in self.NCV_names:
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
#        for sample in set(self.NCV_classified.keys() + [sample.sample_ID for sample in QC_flagged]):
       # for sample_id, warning in self.NCV_classified.items():
         #   self.QC_warnings[sample_id]['NCV_high'] = warning
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

#        for sample in low_NES:
#            self.QC_warnings[sample.sample_ID]['missing_data'] = sample.NonExcludedSites #'Less than 8M reads'
#        for sample in QC_flagged:
#            self.QC_warnings[sample.sample_ID]['QC_fail'] = sample.QCFailure if sample.QCFailure else ''
#            self.QC_warnings[sample.sample_ID]['QC_warn'] = sample.QCWarning if sample.QCWarning else ''



################################################################################################


class PlottPage():
    """Class to preppare data for NCV plots"""
    def __init__(self, batch_id, BDF):
        self.NCV_include        =   NCV.query.filter(NCV.include)
        self.batch_id           =   batch_id
        self.NCV_passed         =   BDF.NCV_passed
        self.NCV_normal         =   BDF.NCV_normal
        self.cases              =   BDF.batch_data(batch_id)  
        self.NCV_stat           =   {'NCV_13':{}, 'NCV_18':{}, 'NCV_21':{}, 'NCV_X':{}, 'NCV_Y' : {}}
        self.coverage_plot      =   {'samples':[],'x_axis':[]}
        self.tris_chrom_abn     =   {'13':{}, '18':{}, '21':{}}
        self.sex_chrom_abn      =   {'X0':{}, 'XXX':{}, 'XXY':{},'XYY':{}}
        self.tris_abn           =   {}
        self.case_size          =   10
        self.abn_size           =   7
        self.X_labels           =   self.make_X_labels()
        self.sample_state_dict  =   {'Probable' : {},'False Positive':{},'Verified':{}, 
                                    "False Negative": {}, "Other": {}, "Suspected": {}}
        self.ncv_abn_colors     =   {"Suspected"    :   '#ffd750', 
                                     'Probable'     :   "#0000FF",
                                     'False Negative':  "#ff6699",
                                     'Verified'     :   "#00CC00",
                                     'Other'        :   "#603116", 
                                     "False Positive":  "#E74C3C"}
        self.many_colors        =   list(['#000000', '#4682B4', '#FFB6C1', '#FFA500', '#FF0000', 
                                        '#00FF00', '#0000FF', '#FFFF00', '#00FFFF', '#FF00FF', 
                                        '#C0C0C0', '#808080', '#800000', '#808000', '#008000', 
                                        '#800080', '#008080', '#000080', '#0b7b47','#7b0b3f','#7478fc']) 
        self.cov_colors         =   [[i]*22 for i in self.many_colors]


    def make_approved_stats(self, chrom):
        NCV_pass = []
        NCV_pass_names = []
        if chrom in ['NCV_X', 'NCV_Y']:
            normal = self.NCV_normal['NCV_XY']
        else:
            normal = self.NCV_normal[chrom]
        for s in normal:
            try: 
                NCV_pass.append(float(s.__dict__[chrom])) 
                NCV_pass_names.append(s.sample_name)
            except:
                logging.exception()
                pass
        return [NCV_pass], [NCV_pass_names], len(normal.all())

    def make_cov_plot_data(self):
        cov = Coverage.query.filter(Coverage.batch_id == self.batch_id) 
        x_axis = range(1,23)
        self.coverage_plot['x_axis'] = x_axis
        for samp in cov:
            samp_cov = []
            for i in x_axis:
                try:
                    samp_cov.append(float(samp.__dict__['Chr'+str(i)+'_Coverage']))
                except:
                    pass
            self.coverage_plot['samples'].append((samp.sample_ID, {'cov':samp_cov, 'samp_id':[samp.sample.sample_name]}))

    def make_X_labels(self):
        X_labels = [s.__dict__['sample_ID'] for s in self.cases]
        return X_labels

    def make_NCV_stat(self):
        for chrom in self.NCV_stat.keys():
            NCV_pass , NCV_pass_names, nr_pass = self.make_approved_stats(chrom) 
            NCV_list = []
            NCV_cases = []
            X_labels = []
            for s in self.cases:
                try:
                    NCV_list.append([s.__dict__['sample_ID'], round(float(s.__dict__[chrom]),2)])
                    NCV_cases.append(round(float(s.__dict__[chrom]),2))
                    X_labels.append(s.__dict__['sample_name'])
                except:
                    #NCV_list.append([s.__dict__['sample_ID'], s.__dict__[chrom]])
                    #NCV_cases.append(s.__dict__[chrom])
                    #X_labels.append(s.__dict__['sample_ID'])
                    pass
            self.NCV_stat[chrom] = {
                'nr_pass' : nr_pass,
                'NCV_list' : NCV_list,
                'NCV_cases' : NCV_cases,
                'nr_cases' :len(NCV_cases),
                'x_axis' : range(2,len(NCV_cases)+2),
                'x_range' : [-1, len(NCV_cases)+3],
                'X_labels' : X_labels,
                'chrom' : chrom,
                'NCV_pass' : NCV_pass,
                'NCV_pass_names' : NCV_pass_names}

    def make_chrom_abn(self): 
        x = 1
        status_x = {'Probable':0.1,'Verified':0.2,'False Positive':0.3,'False Negative':0.4, 'Suspected':0.5, 'Other': 0.6}
        for status in self.sample_state_dict.keys():
            
            self.tris_abn[status] = {'NCV' : [], 's_name' : [], 'x_axis': []}
        for abn in ['13','18','21']:
            for status in self.sample_state_dict.keys():                                      
                self.tris_chrom_abn[abn][status] = {'NCV' : [], 's_name' : [], 'x_axis': [], 'nr': 0}             
                for s in Sample.query.filter(Sample.__dict__['status_T'+abn] == status):
                    S_NCV = NCV.query.filter_by(sample_ID = s.sample_ID).first()
                    NCV_val = S_NCV.__dict__['NCV_' + abn]
                    if S_NCV.include and (NCV_val!= 'NA'):
                        self.tris_abn[status]['NCV'].append(float(NCV_val))
                        self.tris_abn[status]['s_name'].append(s.sample_name)
                        self.tris_abn[status]['x_axis'].append(x+status_x[status])
                        self.tris_chrom_abn[abn][status]['NCV'].append(float(NCV_val))
                        self.tris_chrom_abn[abn][status]['s_name'].append(s.sample_name)
                        self.tris_chrom_abn[abn][status]['x_axis'].append(status_x[status]-0.2)#.append(0)
                        self.tris_chrom_abn[abn][status]['nr']+=1
            x = x+1
        for abn in self.sex_chrom_abn.keys():
            for status in self.sample_state_dict.keys():                                       
                self.sex_chrom_abn[abn][status] = {'NCV_X' : [], 'NCV_Y' : [], 's_name' : [], 'nr_cases':0}   
                cases = Sample.query.filter(Sample.__dict__['status_'+abn] == status)          
                for s in cases:
                    NCV_db = NCV.query.filter_by(sample_ID = s.sample_ID).first()
                    if NCV_db.include and (NCV_db.NCV_X!='NA') and NCV_db.NCV_Y!='NA':
                        self.sex_chrom_abn[abn][status]['NCV_X'].append(float(NCV_db.NCV_X))
                        self.sex_chrom_abn[abn][status]['NCV_Y'].append(float(NCV_db.NCV_Y))
                        self.sex_chrom_abn[abn][status]['s_name'].append(s.sample_name)
                        self.sex_chrom_abn[abn][status]['nr_cases']+=1

################################################################################################


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
        self.batch_names = []
        self.Ratio_13 = {}
        self.Ratio_18 = {}
        self.Ratio_21 = {}
        self.NCD_Y = {}
        self.PCS = {}
        self.FF_Formatted = {}
        self.thresholds = {
            'GCBias': {'upper': 0.5, 'lower': -0.5},
            'NonExcludedSites2Tags': {'upper':1, 'lower':0.8},
            'Tags2IndexedReads': {'upper':0.9, 'lower':0.75},
            'TotalIndexedReads2Clusters': {'upper':1, 'lower':0.7},
            'Library_nM': {'upper':150, 'lower':10, 'wished':40},
            'Ratio_13': {'upper':0.20043, 'lower':0.1996},
            'Ratio_18': {'upper':0.25061, 'lower':0.2495},
            'Ratio_21': {'upper':0.25083, 'lower':0.2492},
            'NCD_Y': {'lower' : 80},
            'FF_Formatted': {'lower':2}} 

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


    def make_FF_Formatted(self):
        i=1
        for batch_id in self.batch_ids:
            self.FF_Formatted[batch_id]={'x':[],'y':[]}
            samps = Sample.query.filter(Sample.batch_id==batch_id)
            for samp in samps:
                FF = samp.FF_Formatted.rstrip('%').lstrip('<')
                try:
                    self.FF_Formatted[batch_id]['y'].append(float(FF))
                    self.FF_Formatted[batch_id]['x'].append(i)
                except:
                    logging.exception('Failed to read FF')
                    pass
            i+=1

    def make_PCS(self):
        i=1
        NCV_all = []
        for batch_id in self.batch_ids:
            samps = NCV.query.filter(NCV.batch_id==batch_id)
            self.PCS[batch_id] = {} #{'x':[],'y':[],'sample':[]}
            for samp in samps:
                if samp.sample_ID.split('-')[0].lower()=='pcs':
                    try:
                        NCV_all.append(float(samp.NCV_X))
                    except:
                        logging.exception()
                        pass
                    try:
                        self.PCS[batch_id][samp.sample_ID] = {'x':[],'y':[],'sample':[]}
                        self.PCS[batch_id][samp.sample_ID]['y'].append(float(samp.NCV_X))
                        self.PCS[batch_id][samp.sample_ID]['x'].append(i)
                        self.PCS[batch_id][samp.sample_ID]['sample'] = samp.sample_ID
                    except:
                        logging.exception()
                        pass
            i+=1
        med = float(statistics.median(NCV_all))
        self.thresholds['PCS'] = {'lower' :med-1.45, 'upper':med +1.45}
 
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
                    logging.exception()
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
                    logging.exception()
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
                    logging.exception()
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
                    logging.exception()
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
                    logging.exception()
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
                except Exception as e:
                    logging.exception(e)
                    pass
            i+=1

    def make_NCD_Y(self):
        i=1
        for batch_id in self.batch_ids:
            self.NCD_Y[batch_id]={'x':[],'y':[]}
            samps = NCV.query.filter(NCV.batch_id==batch_id)
            for samp in samps:
                try:
                    self.NCD_Y[batch_id]['y'].append(float(samp.NCD_Y))
                    self.NCD_Y[batch_id]['x'].append(i)
                except:
                    logging.exception()
                    pass
            i+=1
