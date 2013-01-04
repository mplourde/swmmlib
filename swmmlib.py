import re 
import sys
import os
import copy
import hashlib
from operator import itemgetter
import traceback, code

class INP(object):

    def __init__(self, inp_path, new=False, parameter_name_map=None, require_support_files = False):
        self.inp_path = os.path.abspath(str(inp_path))
        self.parameter_name_map = parameter_name_map
        self.new = new
        self.require_support_files = require_support_files

        inp_path_exists = os.path.isfile(self.inp_path)
        if new == False and not inp_path_exists:
            raise Exception("Error: SWMM_Model: No such INP file: " + self.inp_path)

        self.Tags_fields = ['Type', 'Name', 'Tag']
        self.Tags_dtypes = [str, str, str]
        self.Tags_subclasses = []

        # Hydrology
        ## Raingages
        self.RainGages_fields = ['Name', 'RainType', 'Interval', 'SnowCatch', 'Source', 'SourceName', 'StationID', 'Units']
        self.RainGages_dtypes = [str, str, str, float, str, str, str, str]
        self.RainGages_subclasses = ['Symbols', 'Tags']

        self.Symbols_fields = ['Name', 'XCoordinate', 'YCoordinate']
        self.Symbols_dtypes = [str, float, float]
        self.Symbols_subclasses = []

        ## Hydrographs
        self.Hydrographs_fields = ['UHGroup', 'Month', 'Response', 'R', 'T', 'K', 'IAmax', 'IArec', 'IAini']
        self.Hydrographs_dtypes = [str, str, str, str, float, float, float, float, float, float]
        self.Hydrographs_subclasses = []

        ## SnowPacks
        self.SnowPacks_fields = ['Name', 'PlowMinCoeff', 'PlowMaxCoeff','PlowBaseTemp', 'PlowFFH2OCap', 'PlowInitDepth', 
                'PlowInitFreeH2O', 'PlowImpAreaFrac', 'ImpvMinCoeff', 'ImpvMaxCoeff','ImpvBaseTemp', 'ImpvFFH2OCap', 
                'ImpvInitDepth', 'ImpvInitFreeH2O', 'ImpvTCDepth', 'PervMinCoeff', 'PervMaxCoeff','PervBaseTemp', 
                'PervFFH2OCap', 'PervInitDepth', 'PervInitFreeH2O', 'PervTCDepth', 'RmvlStartDepth', 'H2OshedExitFrac', 
                'Trans_to_ImpvFrac', 'Trans_to_PervFrac', 'MeltFrac', 'Trans_to_SubctchFrac', 'RmvlName']

        self.SnowPacks_dtypes = [str, float, float, float, float, float, float, float, float, float, float, float, 
                float, float, float, float, float, float, float, float, float, float, float, float, float, float, 
                float, float, str]
        self.SnowPacks_subclasses = []

        ## Subcatchments
        self.Subcatchments_fields = ['Name', 'Raingage', 'Outlet', 'Area', 'PctImperv', 'Width', 'PctSlope', 
                'CurbLength', 'SnowPack']
        self.Subcatchments_dtypes = [str, str, str, float, float, float, float, float, str]
        self.Subcatchments_subclasses = ['Subareas', 'Groundwater', 'Infiltration', 'Tags']


        self.Subareas_fields = ['Name', 'NImperv', 'NPerv', 'SImperv', 'SPerv', 'PctZero', 'RouteTo', 'PctRouted']
        self.Subareas_dtypes = [str, float, float, float, float, float, str, float]
        self.Subareas_subclasses = []

        
        self.Infiltration1_fields = ['Name', 'SuctionHead', 'HydCon', 'IMDmax']
        self.Infiltration1_dtypes = [str, float, float, float] 
        self.Infiltration2_fields = ['Name', 'MaxRate', 'MinRate', 'Decay', 'DryTime', 'MaxInfil']
        self.Infiltration2_dtypes = [str, float, float, float, float, float]
        self.Infiltration_fields = self.Infiltration1_fields + self.Infiltration2_fields[1:]
        self.Infiltration_dtypes = self.Infiltration1_dtypes + self.Infiltration2_dtypes[1:]
        self.Infiltration_subclasses = []

        self.Groundwater_fields = ['Name', 'Aquifer', 'GWReceivingNode', 'GWSurfaceElev', 'GWFlowCoeff', 'GWFlowExpon', 
                                   'SWFlowCoeff', 'SWFlowExpon', 'SWGWInteractionCoeff', 'SWFixedDepth', 
                                   'GWThresholdElevation']
        self.Groundwater_dtypes = [str, str, str, float, float, float, float, float, float, float, float]
        self.Groundwater_subclasses = []

        self.PolygonPoints_fields = ['Subcatchment', 'XCoordinate', 'YCoordinate']
        self.PolygonPoints_dtypes = [str, float, float]
        self.PolygonPoints_subclasses = []

        self.Loadings_fields = ['Subcatchment', 'Pollutant', 'Loading']
        self.Loadings_dtypes = [str, str, float]
        self.Loadings_subclasses = []

        ## Aquifers
        self.Aquifers_fields = ['Name', 'Porosity', 'WiltPoint', 'FieldCapacity', 'HydCon', 'CondSlope', 'TensionSlope', 
                'UpperEvap', 'LowerEvap', 'LowerLoss', 'BottomElev', 'WaterTable', 'UpperMoist']
        self.Aquifers_dtypes = [str, float, float, float, float, float, float, float, float, float, float, float, float]
        self.Aquifers_subclasses = []

        # Hydraulics
        ## Nodes
        self.Junctions_fields = ['Name', 'InvertElevation', 'MaxDepth', 'InitDepth', 'SurchargeDepth', 'PondedArea']
        self.Junctions_dtypes = [str, float, float, float, float, float]
        self.Junctions_subclasses = ['Coordinates', 'Tags', 'RDII']

        self.Outfalls_fields = ['Name', 'InvertElevation', 'OutfallType', 'TimeSeriesName', 'TideGate']
        self.Outfalls_dtypes = [str, float, str, str, str]
        self.Outfalls_subclasses = ['Coordinates', 'Tags', 'RDII']

        self.Dividers_fields = ['Name', 'InvertElevation', 'DivertedLink', 'DividerType', 'CutoffFlow', 'CurveName', 
            'MinFlow', 'WeirMaxDepth', 'Coefficient', 'MaxDepth', 'InitDepth', 'SurchargeDepth', 'PondedArea']
        self.Dividers_dtypes = [str, float, str, str, float, str, float, float, float, float, float, float, float]
        self.Dividers_subclasses = ['Coordinates', 'Tags', 'RDII']

        self.Storage_fields = ['Name', 'InvertElevation', 'MaxDepth', 'InitDepth', 'StorageCurve', 'CurveName', 
                'CurveCoeff', 'CurveExponent', 'CurveConstant', 'PondedArea', 'EvapFactor', 'SuctionHead', 
                'Conductivity', 'InitialDeficit']
        self.Storage_dtypes = [str, float, float, float, str, str, float, float, float, float, float, float, float, float]
        self.Storage_subclasses = ['Coordinates', 'Tags', 'RDII']

        self.RDII_fields = ['Name', 'UnitHydrograph', 'SewerArea']
        self.RDII_dtypes = [str, str, float]
        self.RDII_subclasses = []

        self.Coordinates_fields = ['Name', 'XCoordinate', 'YCoordinate']
        self.Coordinates_dtypes = [str, float, float]
        self.Coordinates_subclasses = []

        self.Inflows_fields = ['Node', 'Parameter', 'TimeSeries', 'ParameterType', 'UnitsFactor', 'ScaleFactor', 
                'BaselineValue', 'BaselinePattern']
        self.Inflows_dtypes = [str, str, str, str, float, float, float, str]
        self.Inflows_subclasses = []

        self.DWF_fields = ['Node', 'Parameter', 'AvgValue', 'TimePatterns']
        self.DWF_dtypes = [str, str, float, str]
        self.DWF_subclasses = []

        self.Treatments_fields = ['Node', 'Pollutant', 'Formula']
        self.Treatments_dtypes = [str, str, str]
        self.Treatments_subclasses = []

        ## Links
        self.Conduits_fields = ['Name','InletNode', 'OutletNode', 'Length', 'ManningN', 'InletOffset', 
                'OutletOffset', 'InitFlow', 'MaxFlow']
        self.Conduits_dtypes = [str, str, str, float, float, float, float, float, float]
        self.Conduits_subclasses = ['Losses', 'XSections', 'Tags']

        self.Losses_fields = ['Name', 'EntryLoss', 'ExitLoss', 'AvgLoss', 'FlapGate']
        self.Losses_dtypes = [str, float, float, float, str]
        self.Losses_subclasses = []

        self.XSections_fields = ['Name', 'PipeShape', 'Geom1', 'Geom2', 'Geom3', 'Geom4', 'Barrels', 'CulvertCode']
        self.XSections_dtypes = [str, str, str, str, float, float, float, str]
        self.XSections_subclasses = []

        self.Pumps_fields = ['Name', 'InletNode', 'OutletNode', 'PumpCurve', 'InitStatus', 'StartupDepth', 'ShutoffDepth']
        self.Pumps_dtypes = [str, str, str, str, str, float, float]
        self.Pumps_subclasses = ['Tags']

        self.Orifices_fields = ['Name', 'InletNode', 'OutletNode', 'Type', 'InletOffset', 'DischargeCoeff', 'FlapGate', 
                'MoveTime']
        self.Orifices_dtypes = [str, str, str, str, float, float, str, float]
        self.Orifices_subclasses = ['XSections', 'Tags']

        self.Weirs_fields = ['Name', 'InletNode', 'OutletNode', 'Type', 'InletOffset', 'DischargeCoeff', 'FlapGate', 
                'EndContractions', 'EndCoeff']
        self.Weirs_dtypes = [str, str, str, str, float, float, str, int, float]
        self.Weirs_subclasses = ['XSections', 'Tags']

        self.Outlets_fields = ['Name', 'InletNode', 'OutletNode', 'OutflowHeight', 'OutletType', 'FunctionalCoeff', 
                               'FunctionalExponent', 'CurveName', 'FlapGate']
        self.Outlets_dtypes = [str, str, str, float, str, float, float, str, str]
        self.Outlets_subclasses = ['Tags']

        self.Vertices_fields = ['Link', 'XCoordinate', 'YCoordinate']
        self.Vertices_dtypes = [str, float, float]
        self.Vertices_subclasses = []

        # Quality
        ## Pollutants
        self.Pollutants_fields = ['Name', 'MassUnits', 'RainConcen', 'GWConcen', 'IIConcen', 'DecayCoeff', 'SnowOnly', 
                                  'CoPollutant', 'CoPollutantFraction', 'DWFConcen']
        self.Pollutants_dtypes = [str, str, float, float, float, float, str, str, float, float]
        self.Pollutants_subclasses = []

        self.LandUses_fields = ['Name', 'CleaningInterval', 'Availability', 'LastCleaned']
        self.LandUses_dtypes = [str, float, float, float]
        self.LandUses_subclasses = []

        self.Coverages_fields = ['Subcatchment', 'LandUse', 'PercentArea']
        self.Coverages_dtypes = [str, str, float]
        self.Coverages_subclasses = []

        self.BuildUp_fields = ['LandUse', 'Pollutant', 'Formula', 'Coeff1', 'Coeff2', 'Coeff3', 'TimeSeries', 'Normalizer']
        self.BuildUp_dtypes = [str, str, str, float, float, float, str, str]
        self.BuildUp_subclasses = []

        self.WashOff_fields = ['LandUse', 'Pollutant', 'Formula', 'Coeff1', 'Coeff2', 'CleaningEfficiency', 'BMPEfficiency']
        self.WashOff_dtypes = [str, str, str, float, float, float, float]
        self.WashOff_subclasses = []

        # Options
        self.Options_fields = ['FLOW_UNITS', 'INFILTRATION', 'FLOW_ROUTING', 'START_DATE', 'START_TIME', 
                'REPORT_START_DATE', 'REPORT_START_TIME', 'END_DATE', 'END_TIME', 'SWEEP_START', 'SWEEP_END', 
                'DRY_DAYS', 'REPORT_STEP', 'WET_STEP', 'DRY_STEP', 'ROUTING_STEP', 'ALLOW_PONDING', 'INERTIAL_DAMPING', 
                'VARIABLE_STEP', 'LENGTHENING_STEP', 'MIN_SURFAREA', 'NORMAL_FLOW_LIMITED', 'SKIP_STEADY_STATE', 
                'FORCE_MAIN_EQUATION', 'LINK_OFFSETS', 'MIN_SLOPE', 'IGNORE_RAINFALL', 'IGNORE_GROUNDWATER']
        self.Options_dtypes = [str, str, str, str, str, str, str, str, str, str, str, float, str, 
                               str, str, str, str, str, float, float, float, str, str, str, str, float, str, str]
        self.Options_subclasses = []

        self.Report_fields = ['INPUT', 'CONTROLS', 'SUBCATCHMENTS', 'NODES', 'LINKS']
        self.Report_dtypes = [str, str, str, str, str]
        self.Report_subclasses = []

        # Files
        self.Files_fields = ['Usage', 'FileType', 'FileName']
        self.Files_dtypes = [str, str, str]
        self.Files_subclasses = []

        # Evaporation
        self.Evaporation_fields = ['Type', 'Constant']
        self.Evaporation_subclasses = []

        # Patterns
        #self.patterns_fields = ['Name', 'Type', 'Multiplier']

        # Curves
        self.CurvePoints_fields = ['Curve', 'Type', 'XCoordinate', 'YCoordinate']
        self.CurvePoints_dtypes = [str, str, float, float]
        self.CurvePoints_subclasses = []

        self.TimeSeriesPoints_fields = ['TimeSeries', 'FileName', 'DateTime', 'Duration', 'Value']
        self.TimeSeriesPoints_dtypes = [str, str, str, float, float]
        self.TimeSeriesPoints_subclasses = []

        self.Profiles_fields = ['Profile', 'Links']
        self.Profiles_dtypes = [str, str]
        self.Profiles_subclasses = []

        self.sections_and_tags = [('Notes',               '[TITLE]'),
                                  ('Options',             '[OPTIONS]'),
                                  ('Files',               '[FILES]'),
                                  ('Evaporation',         '[EVAPORATION]'),
                                  ('Junctions',           '[JUNCTIONS]'), 
                                  ('Outfalls',            '[OUTFALLS]'),
                                  ('Dividers',            '[DIVIDERS]'),
                                  ('Storage',             '[STORAGE]'),
                                  ('Coordinates',         '[COORDINATES]'),
                                  ('Conduits',            '[CONDUITS]'),
                                  ('Pumps',               '[PUMPS]'),
                                  ('Orifices',            '[ORIFICES]'),
                                  ('Weirs',               '[WEIRS]'),
                                  ('Outlets',             '[OUTLETS]'),
                                  ('XSections',           '[XSECTIONS]'),
                                  ('Losses',              '[LOSSES]'),
                                  ('RainGages',           '[RAINGAGES]'),
                                  ('Symbols',             '[SYMBOLS]'),
                                  ('Pollutants',          '[POLLUTANTS]'),
                                  ('LandUses',            '[LANDUSES]'),
                                  ('BuildUp',             '[BUILDUP]'),
                                  ('WashOff',             '[WASHOFF]'),
                                  ('Inflows',             '[INFLOWS]'),
                                  ('DWF',                 '[DWF]'),
                                  ('RDII',                '[RDII]'),
                                  ('Aquifers',            '[AQUIFERS]'),
                                  ('Subcatchments',       '[SUBCATCHMENTS]'),
                                  ('Subareas',            '[SUBAREAS]'),
                                  ('Infiltration',        '[INFILTRATION]'),
                                  ('Groundwater',         '[GROUNDWATER]'),
                                  ('Coverages',           '[COVERAGES]'),
                                  ('Loadings',            '[LOADINGS]'),
                                  ('Treatments',          '[TREATMENT]'),
                                  ('Vertices',            '[VERTICES]'),
                                  ('PolygonPoints',       '[POLYGONS]'),
                                  ('Tags',                '[TAGS]'),
                                  ('PatternMultipliers',  '[PATTERNS]'),
                                  ('CurvePoints',         '[CURVES]'),
                                  ('Hydrographs',         '[HYDROGRAPHS]'),
                                  ('SnowPacks',           '[SNOWPACKS]'),
                                  ('TimeSeriesPoints',    '[TIMESERIES]'),
                                  ('Controls',            '[CONTROLS]'),
                                  ('TransectPoints',      '[TRANSECTS]'),
                                  ('Report',              '[REPORT]'),
                                  ('Maps',                '[MAP]'),
                                  ('Profiles',            '[PROFILES]')]

        self.section_labels = dict(self.sections_and_tags)

        self.supported_primary_sections = ['Junctions', 'Outfalls', 'Dividers', 'Storage', 'Conduits', 'Subcatchments', 
                'NodeInflows', 'Pollutants', 'Weirs', 'Loadings', 'Files', 'Report', 'Maps', 'Controls', 'Outlets',
                'Orifices', 'Pumps', 'Aquifers', 'PolygonPoints', 'Vertices', 'RainGages', 'Options', 'Storage', 
                'Treatments', 'Notes', 'PatternMultipliers', 'Evaporation', 'Hydrographs', 'SnowPacks', 'CurvePoints', 
                'LandUses', 'Coverages', 'BuildUp', 'WashOff', 'TimeSeriesPoints', 'Profiles', 'TransectPoints']

        self.inp_lines = []
        self.primary_sections = []
        self.section_locations = {}
        self.unsupported_sections = []
        self.unsupported_sections_ignored = []
        self.section_tags_to_ignore = []
        self.files = {}
        if not self.new:
            with open(self.inp_path, 'r') as f:
                self.text = f.read()

            with open(self.inp_path, 'r') as f:
                self.inp_lines = f.readlines()

            notInNotes = True
            for i, line in enumerate(self.inp_lines):
                self.inp_lines[i] = re.sub('\\xa0', ' ', line) # replace non-breaking spaces with spaces
                if re.match('^[\s]*\[', line): # if this is a tag line...
                    tag = line.strip()
                    if tag == self.section_labels['Notes']:
                        notInNotes = False
                notCommentLine = not re.match('^[\s]*\;', line)
                hasEOLComment = re.search('\;', line)
                if notInNotes and notCommentLine and hasEOLComment: # remove eol comments, unless they are in [TITLE] or 
                    self.inp_lines[i] = line.split(';')[0]
                
            self.cacheSections()
            xml_list = ['<?xml version="1.0"?>\n<INP>\n']
            for section in self.primary_sections:
                xml_list.append(self.get(section, xml=True))
            xml_list.append('</INP>')
            self.xml = ''.join(xml_list)
        else:
            f = open(self.inp_path, 'w')
            f.write('')
            f.close()

    def getINPText(self):
        return ''.join(self.inp_lines)

    def getSupportedSections(self):
        return self.section_labels.keys()

    def getUnsupportedSectionTags(self, ignored=False):
        if ignored:
            return self.unsupported_sections_ignored
        else:
            return self.unsupported_sections

    def setInfiltrationMethod(self, method):
        if method == 1:
            self.Infiltration_fields = self.Infiltration1_fields
        elif method == 2:
            self.Infiltration_fields = self.Infiltration2_fields
        else:
            raise Exception('Error: swmmlib.setInfiltrationMethod: unknown method number ' + str(method))

    def getPrimarySections(self):
        return self.primary_sections

    def getSections(self):
        return self.section_locations.keys()

    def getElementClassFields(self, elclass):
        if elclass in self.section_labels:
            fields = dict(zip(getattr(self, elclass + '_fields'), getattr(self, elclass + '_dtypes')))
            for subclass in getattr(self, elclass + '_subclasses'):
                fields = dict(fields.items() + self.getElementClassFields(subclass).items())
            return fields
        else:
            raise Exception("inpLib does not support the section '" + elclass + "'")

    def cacheSections(self):
        labels2sections = dict(zip(self.section_labels.values(), self.section_labels.keys()))
        label = ""
        section_start = int()
        num_preceding_blanks = int()
        last_line = len(self.inp_lines) - 1
        for i, line in enumerate(self.inp_lines):
            if re.match('^[\s]*\[', line) or (i == last_line):
                if label != "":
                    if label in labels2sections.keys():
                        section = labels2sections[label]
                        if i == last_line:
                            section_end = i + 1
                        else:
                            section_end = i - num_preceding_blanks
                        self.section_locations[section] = (section_start, section_end)
                        if section in self.supported_primary_sections:
                            self.primary_sections.append(section)
                        elif 'NodeInflows' not in self.primary_sections and section == 'DWF' or section == 'Inflows':
                            self.primary_sections.append('NodeInflows')
                    elif label in self.section_tags_to_ignore:
                        self.unsupported_sections_ignored.append(label)
                    else:
                        self.unsupported_sections.append(label)

                label = line.strip().upper()
                section_start = i
                num_preceding_blanks = 0
            elif re.match('^[\s]*$', line):
                if not num_preceding_blanks == 0:
                    num_preceding_blanks = 1
                else:
                    num_preceding_blanks += 1
            else:
                num_preceding_blanks = 0
        self.primary_sections = list(set(self.primary_sections)) # dwf and inflows are both nodeInflow, so get unique
                    
    def put_Losses(self, table, colnames):
        self.put('Losses', table, colnames, descriptions=True, description_col='LossesDescription')
        
    def put_Subcatchments(self, table, colnames):
        self.put('Subcatchments', table, colnames, descriptions=True)
        self.put('Subareas', table, colnames, descriptions=True, description_col = 'SubareasDescription')
        aquifer_col_num = colnames.index('Aquifer')
        table2 = [row for row in table if row[aquifer_col_num] is not None]
        self.put('Groundwater', table2, colnames, descriptions = True, description_col='GWDescription')
        if table[0][colnames.index('SuctionHead')] is None:
            self.setInfiltrationMethod(2)
        else:
            self.setInfiltrationMethod(1)
        self.put('Infiltration', table, colnames, descriptions = True, description_col="InfiltrationDescription")
        self.put_Tags('Subcatch', table, colnames)

    def put_Weirs(self, table, colnames):
        self.put('Weirs', table, colnames, descriptions=True)
        self.put('XSections', table, colnames, descriptions=True, description_col='XSectionsDescription')
        self.put_Tags('Link', table, colnames)

    def put_Outlets(self, table, colnames):
        self.put('Outlets', table, colnames, descriptions=True)
        self.put_Tags('Link', table, colnames)

    def put_RainGages(self, table, colnames):
        self.put('RainGages', table, colnames, descriptions=True)
        self.put_Symbols(table, colnames)
        self.put_Tags('Gage', table, colnames)

#    # alternative implementation of put_SnowPacks
#    def put_SnowPacks(self, table, colnames):
#        allfields = self.SnowPacks_fields
#        fields_by_catchtype = {'PLOWABLE' : allfields[1:8], 'IMPERVIOUS' : allfields[8:15], 
#                               'PERVIOUS' : allfields[15:22], 'REMOVAL' : allfields[22:29]}
#        new_table = []
#        for row in table:
#            namesAndValues = zip(colnames, row)
#            print row
#            for catchtype, fields in fields_by_catchtype.items():
#                print catchtype
#                ct_namesAndValues = [(name, param) for name, param in namesAndValues if name in fields]
#                ct_namesAndValues.sort(key=lambda nameAndValue: fields.index(nameAndValue[0]))
#                _, ct_values = zip(*ct_namesAndValues)
#                print ct_values
#                code.interact(local=locals())
#                if all(value is not None for value in ct_values):
#                    new_table.append([row[colnames.index('Name')]] + [catchtype] + list(ct_values))
#
#        new_colnames = ['Name', 'CatchmentType', 'Param1', 'Param2', 'Param3', 'Param4', 'Param5', 'Param6', 'Param7']
#        self.put('SnowPacks', new_table, new_colnames, alt_fields=new_colnames)
        
    def put_SnowPacks(self, table, colnames):
        section = 'SnowPacks'
        fields = getattr(self, section + '_fields')
        # 'PLOWABLE' : fields[1:8], 'IMPERVIOUS' : fields[8:15], 'PERVIOUS' : fields[15:22], 'REMOVAL' : fields[22:29]
        sp_dict = {0:'PLOWABLE', 1:'IMPERVIOUS', 2:'PERVIOUS', 3:'REMOVAL'}
        new_table = []
        for row in table:
            desc_added = False
            for i in range(4):
                new_line = []
                for field in fields[i*7+1:(i+1)*7+1]:
                    new_line.append( row[colnames.index(field)] )
                if new_line != [None]*7:
                    new_row = tuple( [row[1]] + [sp_dict[i]] + new_line ) 
                    if not desc_added:
                        new_row = new_row + (row.Description.strip('\\n'), )
                        desc_added = True
                    else:
                        new_row = new_row + (None, )
                    new_table.append(new_row)

        new_colnames = ['Name', 'CatchmentType', 'Param1', 'Param2', 'Param3', 'Param4', 'Param5', 'Param6', 'Param7', 
                'Description']
        self.put('SnowPacks', new_table, new_colnames, alt_fields=new_colnames, descriptions=True)

    def put_Hydrographs(self, table, colnames):
        rg_index = colnames.index('RainGage')
        rg_rows = []
        table_no_rg = []
        current_uh = ''
        current_rows = []
        colnames_no_rg = copy.copy(colnames)
        hydrograph_index = colnames_no_rg.index('UHGroup')
        month_index = colnames_no_rg.index('Month')
        months = ['All', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
        for i, row in enumerate(table):
            uh = row[colnames.index('UHGroup')]
            if uh != current_uh:
                if current_rows:
                    current_rows.sort(key = lambda x: (x[hydrograph_index], months.index(x[month_index])))
                    table_no_rg.extend(current_rows)
                current_rows = []
                rg_row = [None for i in xrange(len(colnames_no_rg)-2)]
                rg_row[0] = row[colnames.index('OBJECTID')]
                rg_row[1] = row[colnames.index('Name')]
                rg_row[2] = row[colnames.index('UHGroup')]
                rg_row[3] = row[colnames.index('RainGage')]
                rg_row[-1] = row[colnames.index('RainGageDescription')]
                table_no_rg.append(rg_row)
                current_uh = uh
            row = [item for j, item in enumerate(row) 
                    if j not in (colnames.index('RainGage'), colnames.index('RainGageDescription'))]
            current_rows.append(row)
            if i == (len(table) - 1):
                if current_rows:
                    table_no_rg.extend(current_rows)

        colnames_no_rg.remove('RainGage')
        colnames_no_rg.remove('RainGageDescription')
        
        self.put('Hydrographs', table_no_rg, colnames_no_rg, alt_fields = self.Hydrographs_fields, descriptions=True)

    def put_Pumps(self, table, colnames):
        self.put('Pumps', table, colnames, descriptions=True)
        self.put_Tags('Link', table, colnames)

    def put_Pollutants(self, table, colnames):
        self.put('Pollutants', table, colnames, descriptions=True)

    def put_LandUses(self, table, colnames):
        self.put('LandUses', table, colnames, descriptions=True)
        
    def put_Coverages(self, table, colnames):
        self.put('Coverages', table, colnames, descriptions=True)

    def put_Loadings(self, table, colnames):
        self.put('Loadings', table, colnames, descriptions=True)

    def put_BuildUp(self, table, colnames):
        self.put('BuildUp', table, colnames, descriptions=True)

    def put_WashOff(self, table, colnames):
        self.put('WashOff', table, colnames, descriptions=True)

    def put_CurvePoints(self, table, colnames):
        curve_index = colnames.index('Curve')
        type_index = colnames.index('Type')
        ord_index = colnames.index('Ordinal')
        x_index = colnames.index('XCoordinate')
        y_index = colnames.index('YCoordinate')
        description_index = colnames.index('Description')

        curves_types = [(row[curve_index], row[type_index]) for row in table]
        curves_types = list(set(curves_types))

        for tup in curves_types:
            curve, curve_type = tup
            sub_table = [row for row in table if row[curve_index] == curve]
            sub_table = sorted(sub_table, key = itemgetter(ord_index))
            
            for i, row in enumerate(sub_table):
                if i != 0: #row[description_index] = None
                    row[type_index] = ' '*len(curve_type)
                else:
                    sub_table = [tuple(None for i in range(len(row)))] + sub_table
                    #sub_table = [None for item in row] + sub_table

            self.put('CurvePoints', sub_table, colnames, descriptions=True)

    def put_TimeSeriesPoints(self, table, colnames):
        description_index = colnames.index('Description')
        ts_index = colnames.index('TimeSeries')
        ord_index = colnames.index('Ordinal')
        file_index = colnames.index('FileName')
        dtime_index = colnames.index('DateTime')
        duration_index = colnames.index('Duration')
        
        series = [row[ts_index] for row in table]
        series = list(set(series))

        for ts in series:
            sub_table = [row for row in table if row[ts_index] == ts]
            sub_table = sorted(sub_table, key = itemgetter(ord_index))

            if len(sub_table) == 1:
                fname = sub_table[0][file_index]
                sub_table[0][file_index] = 'FILE  ' + fname 
                sub_table = [tuple(None for i in range(len(row)))] + sub_table # add empty row before
            else:
                for i, row in enumerate(sub_table):
                    if i == 0:
                        #row[description_index] = None
                        sub_table = [tuple(None for i in range(len(row)))] + sub_table # add empty row before

                    if row[dtime_index] is not None:
                        row[dtime_index] = row[dtime_index].strftime(format = '%m/%d/%Y %H:%M:%S')

            self.put('TimeSeriesPoints', sub_table, colnames, descriptions=True)

    def put_Orifices(self, table, colnames):
        self.put('Orifices', table, colnames, descriptions=True)
        self.put('XSections', table, colnames, descriptions=True, description_col = 'XSectionsDescription')
        self.put_Tags('Link', table, colnames)

    def put_NodeInflows(self, table, colnames):
        name_col_num = colnames.index('Name')
        for row in table:
            row[name_col_num] = row[name_col_num].split(':')[0]

        timeseries_col_num = colnames.index('TimeSeries')
        avgvalue_col_num = colnames.index('AvgValue')
        table1 = [row for row in table if row[timeseries_col_num] is not None]
        table2 = [row for row in table if row[avgvalue_col_num] is not None]
        self.put('Inflows', table1, colnames, descriptions=True, description_col='InflowsDescription')
        self.put('DWF', table2, colnames, descriptions=True, description_col='DWFDescription')

    def put_Profiles(self, table, colnames):

        prof_index = colnames.index('Profile')
        link_index = colnames.index('Link')
        ord_index = colnames.index('Ordinal')
        profile_names = [row[prof_index] for row in table]
        profile_names = sorted(list(set(profile_names)))

        formatted_table = []
        for profile in profile_names:
            sub_table = [row for row in table if row[prof_index] == profile]
            sub_table = sorted(sub_table, key = itemgetter(ord_index))

            current_link_str = ''
            num_links_per_line = 5
            subtable_len = len(sub_table)
            for i, row in enumerate(sub_table):
                if not re.search('^"', profile):
                    profile_name = '"' + profile + '"'
                else:
                    profile_name  = profile

                if i > 0 and (i % num_links_per_line) == 0:
                    formatted_table.append([profile_name, current_link_str])
                    current_link_str = row[link_index] + ' '
                    if i == (subtable_len -1):
                        formatted_table.append([profile_name, current_link_str])
                elif i == (subtable_len - 1):
                    current_link_str += row[link_index]
                    formatted_table.append([profile_name, current_link_str])
                else:
                    current_link_str += row[link_index] + ' '

        new_colnames = ['Profile', 'Links']
        self.put('Profiles', formatted_table, new_colnames, alt_fields = new_colnames)

    def put_Controls(self, table, colnames):
        ord_index = colnames.index('Ordinal')
        table = sorted(table, key = itemgetter(ord_index))
        lines = [self.section_labels['Controls']]
        for row in table:
            rule_name = row[colnames.index('RuleName')]
            description = row[colnames.index('Description')]
            if description is not None:
                description = description.decode('string-escape')
                #description = description.strip('\n')
                description = description.split('\n')
                description = [';' + line for line in description]
                lines.extend(description)

            lines.append('RULE ' + rule_name)
            rule_text = row[colnames.index('RuleText')]
            rule_text = rule_text.decode('string-escape')
            rule_text = rule_text.split('\n')
            for line in rule_text:
                lines.append(line)

        lines = [line + '\n' for line in lines]
        self.inp_lines.extend(lines)
        self.cacheSections()

    def put_TransectPoints(self, table, colnames):
        transect_ix = colnames.index('TransectName')
        ordinal_ix = colnames.index('Ordinal')
        table = sorted(table, key=itemgetter(transect_ix, ordinal_ix))

        lines = [self.section_labels['TransectPoints']]
        spacer = ' ' * 5
        
        lbankr_ix = colnames.index('LeftBankRoughness')
        rbankr_ix = colnames.index('RightBankRoughness')
        croughness_ix = colnames.index('ChannelRoughness')
        lbanks_ix = colnames.index('LeftBankStation')
        rbanks_ix = colnames.index('RightBankStation')
        smod_ix = colnames.index('StationsModifier')
        emod_ix = colnames.index('ElevationsModifier')
        mmod_ix = colnames.index('MeanderModifier')
        desc_ix = colnames.index('Description')
        sfeet_ix = colnames.index('Station_ft')
        efeet_ix = colnames.index('Elevation_ft')
        stationcount_ix = colnames.index('StationCount')

        nc_ixs = [lbankr_ix, rbankr_ix, croughness_ix]
        x1_left_ixs = [transect_ix, stationcount_ix, lbanks_ix, rbanks_ix]
        x1_right_ixs = [mmod_ix, smod_ix, emod_ix]
        x1_num_filler_zeros = 2
        num_tpoints_per_line = 5
        
        currentline_point_count = 0
        stations_written = 0
        total_station_count = 0
        for row in table:
            ordinal = row[ordinal_ix]
            if ordinal == 1:
                lines.append('')
                desc = row[desc_ix]
                if desc is not None:
                    #desc = desc.strip('\n')
                    desc = desc.decode('string-escape')
                    desc = desc.split('\n')
                    desc = [';' + line for line in desc]
                    lines.extend(desc)

                nc_line = ['NC'] + [str(row[ix]) for ix in nc_ixs]
                nc_line = spacer.join(nc_line)
                lines.append(nc_line)

                x1_line = ['X1'] + [str(row[ix]) for ix in x1_left_ixs] + ['0' for i in xrange(x1_num_filler_zeros)] + [str(row[ix]) for ix in x1_right_ixs]
                x1_line = spacer.join(x1_line)
                lines.append(x1_line)

                current_gr_line = spacer.join(['GR', str(row[efeet_ix]), str(row[sfeet_ix])])
                currentline_point_count = 1
                stations_written = 1
                total_station_count = row[stationcount_ix]
            else:
                if currentline_point_count < num_tpoints_per_line:
                    current_gr_line = spacer.join([current_gr_line, str(row[efeet_ix]), str(row[sfeet_ix])])
                    currentline_point_count += 1
                    stations_written += 1
                    if stations_written == total_station_count:
                        lines.append(current_gr_line)
                else:
                    lines.append(current_gr_line)
                    current_gr_line = spacer.join(['GR', str(row[efeet_ix]), str(row[sfeet_ix])])
                    currentline_point_count = 1
                    stations_written += 1
                    if stations_written == total_station_count:
                        lines.append(current_gr_line)
        lines = [line + '\n' for line in lines]
        self.inp_lines.extend(lines)
        self.cacheSections()

    def put_Treatments(self, table, colnames):
        self.put('Treatments', table, colnames, descriptions=True)

    def put_Aquifers(self, table, colnames):
        self.put('Aquifers', table, colnames, descriptions=True)

    def put_Vertices(self, table, colnames):
        table = [list(row) for row in table]
        for row in table:
            name_col_num = colnames.index('Name')
            name_split = row[name_col_num].split(':')
            name = name_split[0]
            ordinal = int(name_split[1])
            row[name_col_num] = name
            row.append(ordinal)
        ord_col_num = colnames.index('Ordinal')
        table = sorted(table, key=itemgetter(name_col_num, ord_col_num))
        self.put('Vertices', table, colnames, descriptions=True)

    def put_PolygonPoints(self, table, colnames):
        table = [list(row) for row in table]
        for row in table:
            name_col_num = colnames.index('Name')
            name_split = row[name_col_num].split(':')
            name = name_split[0]
            ordinal = int(name_split[1])
            row[name_col_num] = name
            row.append(ordinal)
        ord_col_num = colnames.index('Ordinal')
        table = sorted(table, key=itemgetter(name_col_num, ord_col_num))

        self.put('PolygonPoints', table, colnames, descriptions=True)

    def put_Notes(self, table, colnames):
        notes = table[0][colnames.index('NotesText')]
        notes = notes.decode('string-escape')
        notes = notes.split('\n')
        notes = [line + '\n' for line in notes]
        temp_inp_lines = self.inp_lines
        self.inp_lines = ['[TITLE]\n']
        self.inp_lines.extend(notes)
        self.inp_lines.append('\n')
        self.inp_lines.extend(temp_inp_lines)
        self.cacheSections()

    def put_Options(self, table, colnames):
        row = table[0]
        fields = self.Options_fields
        lines = ['' for i in xrange(len(fields) + 1)]
        label_col_width = max([len(field) for field in fields])
        format_str = '{:<' + str(label_col_width) + '}'
        lines[0] = self.section_labels['Options'] + '\n'
        for i, field in enumerate(fields):
            value = row[colnames.index(field)]
            if value is None:
                continue
            elif isinstance(value, float):
                if value == int(value):
                    value = int(value)
            line = format_str.format(field) + '\t\t' + str(value) + '\n'
            lines[i + 1] = line
        lines.append('\n')
        lines.extend(self.inp_lines)
        self.inp_lines = lines
        self.cacheSections()

    def put_Report(self, table, colnames):
        row = table[0]
        fields = self.Report_fields
        lines = ['' for i in xrange(len(fields) + 1)]
        label_col_width = max([len(field) for field in fields])
        format_str = '{:<' + str(label_col_width) + '}'
        lines[0] = self.section_labels['Report'] + '\n'
        for i, field in enumerate(fields):
            value = row[colnames.index(field)]
            line = format_str.format(field) + '\t\t' + str(value) + '\n'
            lines[i + 1] = line
        lines.append('\n')
        lines.extend(self.inp_lines)
        self.inp_lines = lines
        self.cacheSections()

    def put_Maps(self, table, colnames):
        row = table[0]
        fields = self.Report_fields
        lines = ['' for i in xrange(3)]
        lines[0] = self.section_labels['Maps']
        dim_names = ['LLXCoordinate', 'LLYCoordinate', 'URXCoordinate', 'URYCoordinate']
        dims = [str(row[colnames.index(dim_name)]) for dim_name in dim_names]
        dims_line = ' '.join(['DIMENSIONS'] + dims)
        lines[1] = dims_line
        lines[2] = 'Units     ' + row[colnames.index('Units')]
        lines = [line + '\n' for line in lines]
        self.inp_lines.extend(lines)
        self.cacheSections()

    def put_Evaporation(self, table, colnames):
        row = table[0]
        lines = []
        lines = [self.section_labels['Evaporation'],
                 ';;Type       Parameters',
                 ';;---------- ----------']

        spacer = ' ' * 5
        evaptype = row[colnames.index('Type')]
        params = row[colnames.index('Parameters')]
        recovery = row[colnames.index('Recovery')]
        dryonly = row[colnames.index('DryOnly')]

        formatted_data = [spacer.join([evaptype, params])]
        if recovery is not None:
            formatted_data.append(spacer.join(['RECOVERY', recovery]))

        if dryonly is not None:
            formatted_data.append(spacer.join(['DRY_ONLY', dryonly]))

        lines.extend(formatted_data)
        lines = [line + '\n' for line in lines]
        self.inp_lines.extend(lines)
        self.cacheSections()

    def put_PatternMultipliers(self, table, colnames):
        pat_index = colnames.index('Pattern')
        type_index = colnames.index('Type')
        ord_index = colnames.index('Ordinal')
        mult_index = colnames.index('Multiplier')
        desc_index = colnames.index('Description')
        patterns_types = [(row[pat_index], row[type_index]) for row in table]
        patterns_types = list(set(patterns_types))

        for tup in patterns_types:
            pat, pat_type = tup
            sub_table = [row for row in table if row[pat_index] == pat]
            sub_table = sorted(sub_table, key = itemgetter(ord_index))

            if pat_type == 'MONTHLY':
                num_multipliers = 12
                multiplier_col_width = 6
            elif pat_type == 'DAILY':
                num_multipliers = 7
                multiplier_col_width = 7
            elif pat_type == 'HOURLY':
                num_multipliers = 24
                multiplier_col_width = 6
            elif pat_type == 'WEEKEND':
                num_multipliers = 24
                multiplier_col_width = 6
            else:
                raise Exception("Error: swmmlib.put_PatternMulitpliers: Unexpected pattern type encountered. Pattern: " \
                        + str(pat) + ", Type: " + str(type))

            if (num_multipliers % multiplier_col_width) != 0:
                raise Exception('Error: swmmlib.put_PatternMultipliers: Unexpected number of columns found in pattern ' \
                        + str(pat) + ' of type ' + str(type))

            if len(sub_table) != num_multipliers:
                raise Exception('Error: swmmlib.put_PatternMultipliers: Pattern ' + str(pat) + ' of type ' + str(type) \
                        + 'has more multipliers than expected.')
            else:
                formatted_table = []
                desc = sub_table[0][desc_index]
                for i in xrange(num_multipliers / multiplier_col_width):
                    start_row = i * multiplier_col_width
                    end_row = (i+1) * multiplier_col_width
                    row_multipliers = [str(row[mult_index]) for row in sub_table[start_row:end_row]]
                    spacer = ' '*2
                    row_multipliers =  spacer.join(row_multipliers)
                    if i == 0:
                        row = [pat, pat_type, row_multipliers, desc]
                    else:
                        type_spacer = len(pat_type) * ' '
                        row = [pat, type_spacer, row_multipliers, None]

                    formatted_table.append(row)

                alt_fields = ['Name', 'Type', 'Multipliers']
                new_colnames = copy.copy(alt_fields)
                new_colnames.append('Description')
                formatted_table = [tuple(None for i in range(len(formatted_table[0])))] + formatted_table
                self.put('PatternMultipliers', table = formatted_table, colnames = new_colnames, descriptions=True, alt_fields=alt_fields)

    def put_Files(self, table, colnames):
        ord_ix = colnames.index('Ordinal')
        table = sorted(table, key = itemgetter(ord_ix))
        self.put('Files', table, colnames)

    def put_Conduits(self, table, colnames):
        self.put('Conduits', table, colnames, descriptions=True)
        self.put('XSections', table, colnames, descriptions=True, description_col='XSectionsDescription')
        losses_colnums = [i for i, colname in enumerate(colnames) if colname in self.Losses_fields[1:]]
        losses_table = [row for row in table if [value for i, value in enumerate(row) if i in losses_colnums] != [0, 0, 0, 'NO']]
        self.put('Losses', losses_table, colnames, descriptions=True, description_col='LossesDescription')
        self.put_Tags('Link', table, colnames)

    def put_Coordinates(self, table, colnames):
        coor_colnums = [i for i, colname in enumerate(colnames) 
                if colname in self.Coordinates_fields[1:] + ['CoordinateDescription']]
        coor_table = [row for row in table 
                if [value for i, value in enumerate(row) if i in coor_colnums] != [None, None, None]]
        self.put('Coordinates', coor_table, colnames, descriptions=True, description_col='CoordinateDescription')

    def put_Symbols(self, table, colnames):
        symb_colnums = [i for i, colname in enumerate(colnames) 
                if colname in self.Symbols_fields[1:] + ['CoordinateDescription']]
        symb_table = [row for row in table if [value for i, value in enumerate(row) 
            if i in symb_colnums] != [None, None, None]]
        self.put('Symbols', symb_table, colnames, descriptions=True, description_col='CoordinateDescription')
        
    def put_Junctions(self, table, colnames):
        self.put('Junctions', table, colnames, descriptions=True)
        self.put_Coordinates(table, colnames)
        self.put_Tags('Node', table, colnames)
        rdii_table = [row for row in table if row[colnames.index('UnitHydrograph')] is not None]
        self.put('RDII', rdii_table, colnames, descriptions=True, description_col = 'RDIIDescription')

    def put_Outfalls(self, table, colnames):
        self.put('Outfalls', table, colnames, descriptions=True)
        self.put_Coordinates(table, colnames)
        self.put_Tags('Node', table, colnames)
        rdii_table = [row for row in table if row[colnames.index('UnitHydrograph')] is not None]
        self.put('RDII', rdii_table, colnames, descriptions=True, description_col = 'RDIIDescription')

    def put_Dividers(self, table, colnames):
        self.put('Dividers', table, colnames, descriptions=True)
        self.put_Coordinates(table, colnames)
        self.put_Tags('Node', table, colnames)
        rdii_table = [row for row in table if row[colnames.index('UnitHydrograph')] is not None]
        self.put('RDII', rdii_table, colnames, descriptions=True, description_col = 'RDIIDescription')

    def put_Storage(self, table, colnames):
        self.put('Storage', table, colnames, descriptions=True)
        self.put_Coordinates(table, colnames)
        self.put_Tags('Node', table, colnames)
        rdii_table = [row for row in table if row[colnames.index('UnitHydrograph')] is not None]
        self.put('RDII', rdii_table, colnames, descriptions=True, description_col='RDIIDescription')

    def put_Tags(self, element_type, table, colnames):
        section_exists = False
        section = 'Tags'
        if section in self.section_locations.keys():
            section_exists = True
            section_end = self.section_locations[section][1]
        else:
            self.inp_lines.append('\n')
            self.inp_lines.append(self.section_labels[section] + '\n')
            section_end = len(self.inp_lines)

        format_str = '{:<25}'
        tags_inserted = 0
        for row in table:
            name = str(row[colnames.index('Name')])
            tag = row[colnames.index('Tag')]
            if tag is None:
                continue
            else:
                tag = str(tag)
            newline = [element_type, name, tag]
            newline = [format_str.format(value) + ' ' for value in newline]
            newline = ''.join(newline) + '\n'
            self.inp_lines.insert(section_end + tags_inserted, newline)
            tags_inserted += 1

        self.cacheSections()

    def put(self, section, table, colnames, descriptions = False, description_col = 'Description', 
            beginning=False, alt_fields=None):

        if alt_fields is None:
            element_fields = getattr(self, section + '_fields')
        else:
            element_fields = alt_fields

        field_widths = [len(field) for field in element_fields]
        field_width = max(field_widths)
        field_separator = ' '*3
        data_width = field_width + len(field_separator)
        format_str1 = '{:<' + str(field_width) + '}'
        format_str2 = '{:<' + str(data_width) + '}'

        section_exists = False
        if section in self.section_locations.keys():
            section_exists = True
            section_end = self.section_locations[section][1]
        else:
            if beginning:
                if 'Options' in self.section_locations.keys():
                    options_end = self.section_locations['Options'][1]
                    inp_lines_head = self.inp_lines[:options_end]
                    inp_lines_tail = self.inp_lines[options_end:]
                    self.inp_lines = inp_lines_head
                else:
                    inp_lines_tail = self.inp_lines
                    self.inp_lines = []

            self.inp_lines.append('\n')
            self.inp_lines.append(self.section_labels[section] + '\n')

            fields_formatted = [format_str1.format(field_name) for field_name in element_fields]
            fields_formatted = ';;' + field_separator.join(fields_formatted)
            self.inp_lines.append(fields_formatted + '\n')

            divider = ['-'*field_width for i in xrange(len(element_fields))]
            divider = ';;' + field_separator.join(divider)
            self.inp_lines.append(divider + '\n')

            section_end = len(self.inp_lines) 

        for i, row in enumerate(table):
            if descriptions:
                description_col_num = colnames.index(description_col)
                description = row[description_col_num]
                if description is not None:
                    description = description.decode('string-escape')
                    description = description.split('\n')
                    description = [';' + line + '\n' for line in description]
                    for line in description:
                        self.inp_lines.insert(section_end, line)
                        section_end += 1

            formatted_row = []
            for field in element_fields:
                value = row[colnames.index(field)]
                if value is None:
                    value = ''
                elif isinstance(value, float):
                    if value == int(value):
                        value = int(value)
                value = str(value)
                if len(value) >= data_width - 1:
                    value = value + '  '
                formatted_row.append(format_str2.format(value))
            formatted_row[0] = formatted_row[0] + '  '
            formatted_row = ''.join(formatted_row) + '\n'
            self.inp_lines.insert(section_end, formatted_row)
            section_end += 1

        if beginning:
            self.inp_lines.extend(inp_lines_tail)

        self.cacheSections()
    
    def getSection(self, section):
        if section in self.section_locations.keys():
            location = self.section_locations[section]
            start, end = location
            return self.inp_lines[start:end]
        else:
            raise Exception('Error: swmmlib.getSection: No such section ' + section)

    def orderINP(self):
        sections = self.section_locations.keys()
        sections_order = [section for section, tag in self.sections_and_tags]
        sections_ordered = [section for section in sections_order if section in sections]
        new_inp_lines = []
        for section in sections_ordered:
            new_inp_lines.extend(self.getSection(section))
            new_inp_lines.append('\n')
        self.inp_lines = new_inp_lines
        self.cacheSections()

    def temp(self, section):
        path = os.path.join(os.environ.get('TEMP'), 'HHMODEL_temp')
        with open(path, 'w') as f:
            f.write(self.get(section, xml=True))

        return path

    def write(self, preamble = None):
        self.orderINP()
        with open(self.inp_path, 'wb') as f:
            if preamble is not None:
                if isinstance(preamble, str):
                    preamble = preamble.split('\n')

                if isinstance(preamble, list):
                    for i, line in enumerate(preamble):
                        preamble[i] = ';; ' + line.strip() + '\n'
                        if i == len(preamble) - 1:
                            preamble[i] = preamble[i] + '\n\n'
                f.writelines(preamble)
            f.writelines(self.inp_lines)

    # Hydrology
    ## Rain Gages
    def get_RainGages(self):
        section = 'RainGages'
        if section not in self.section_locations.keys():
            return []

        section_start = self.section_locations[section][0]
        section_end = self.section_locations[section][1]
        section_lines = self.inp_lines[section_start:section_end]
        fields = getattr(self, section + '_fields')
        dtypes = getattr(self, section + '_dtypes')

        elements = []
        description = None
        past_header = False
        for i, line in enumerate(section_lines):
            if (re.match('^[\s]*\;\;', line) and not past_header) or re.match('^[\s]*$', line) or re.match('^[\s]*\[', line):
                continue
            if re.match('^[\s]*\;', line):
                past_header = True
                line = line.strip('\;')
                if description is None: description = line
                else: description = description + line
                continue
            else:
                past_header = True
                if re.search(';', line):
                    line, eol_desc = re.split('[ ;]*;', line, maxsplit=1)
                    if description:
                        description = description + eol_desc
                    else:
                        description = eol_desc

                line = line.split()

                if len(line) != len(fields):
                    if len(line) == (len(fields)-2) and line[fields.index('Source')] == 'TIMESERIES':
                        line.extend([None, None])
                    else:
                        raise Exception("Error: SMMIO: get_RainGages: Unexpected line format encountered: " + str(line))

                for j, value in enumerate(line):
                    if value is not None:
                        line[j] = dtypes[j](value)
                params = dict(zip(fields, line))
                params['Description'] = re.sub('\n$', '', description, count = 1) if description is not None else None
                if params['Source'] == 'FILE' and self.require_support_files:
                    filepath = os.path.join(os.path.dirname(self.inp_path), params['SourceName'].strip(' \t\n"'))
                    if not os.path.exists(filepath):
                        raise Exception("Can't find support file '" + filepath + "' referenced in [RAINGAGES]")
                    elif os.path.exists(filepath):
                        params['SourceName'] = '"' + os.path.basename(filepath) + '"'
                        with open(filepath, 'rb') as f:
                            fcontents = f.read()
                        fbuffer = buffer(fcontents)
                        md5 = hashlib.md5(fcontents).hexdigest()
                        params['FileMD5'] = md5
                        self.files[md5] = fbuffer
                else:
                    params['FileMD5'] = None

                elements.append(params)
                description = None
    
        if len(elements) > 0:
            for subclass in getattr(self, section + '_subclasses'):
                elements = getattr(self, 'assign_' + subclass)(section, elements)

        return elements

    def get_Hydrographs(self):
        section = 'Hydrographs'
        if section not in self.section_locations.keys():
            return []

        section_start = self.section_locations[section][0]
        section_end = self.section_locations[section][1]
        section_lines = self.inp_lines[section_start:section_end]
        fields = getattr(self, section + '_fields')
        dtypes = getattr(self, section + '_dtypes')

        elements = []
        raingages_by_group = {}
        raingage = None
        past_header = False
        section_lines = [line for line in section_lines if len(line.strip()) > 0]
        #section_lines = sorted(section_lines, key=lambda x: x.split()[0])
        description = None
        for i, line in enumerate(section_lines):
            if (re.match('^[\s]*\;', line) and not past_header) or re.match('^[\s]*$', line) or re.match('^[\s]*\[', line):
                continue
            if re.match('^[\s]*\;', line):
                past_header = True
                line = line.strip('\;')
                if description is None: description = line
                else: description = description + line
                continue
            else:
                past_header = True
                if re.search(';', line):
                    line, eol_desc = re.split('[ ;]*;', line, maxsplit=1)
                    if description:
                        description = description + eol_desc
                    else:
                        description = eol_desc

                line = line.split()
                group = line[0]
                if len(line) == 2:
                    raingage = line[1]
                    raingages_by_group[group] = {'gage' : raingage,
                                                 'desc' : re.sub('\n$', '', description, count = 1) if description is not None else None}
                else:
                    if len(line) == 14:
                        IAnumbers = line[11:14]
                        shortterm = line[:2] + ['Short'] + line[2:5] + IAnumbers
                        mediumterm = line[:2] + ['Medium'] + line[5:8] + IAnumbers
                        longterm = line[:2] + ['Long'] + line[8:11] + IAnumbers
                        element_lines = [shortterm, mediumterm, longterm]
                    elif len(line) == 9:
                        element_lines = [line]
                    else:
                        raise Exception('Error: swmmlib.get_Hydrographs: Unexpected line format encountered: ' + str(line))

                    for line in element_lines:
                        #line.insert(fields.index('RainGage'), raingages_by_group[group]['gage'])
                        if len(line) == len(fields):
                            for j, value in enumerate(line):
                                if value is not None:
                                    line[j] = dtypes[j](value)

                            params = dict(zip(fields, line))
                            params['Name'] = ':'.join([params['UHGroup'],
                                                       params['Month'],
                                                       params['Response']])
                            params['Description'] = re.sub('\n$', '', description, count = 1) if description is not None else None
                            elements.append(params)
                        else:
                            raise Exception('Error: swmmlib.get_Hydrographs: Unexpected line format encountered: ' + str(line))

                description = None

        for element in elements:
            if element['UHGroup'] in raingages_by_group.keys():
                raingage = raingages_by_group[element['UHGroup']]
                element['RainGage'] = raingage['gage']
                element['RainGageDescription'] = raingage['desc']
            else:
                raise Exception('Error: swmmlib.get_Hydrographs: Missing raingage for ' + element['UHGroup'])

        return elements

    def get_SnowPacks(self):
        section = 'SnowPacks'
        if section not in self.section_locations.keys():
            return []

        section_start = self.section_locations[section][0]
        section_end = self.section_locations[section][1]
        section_lines = self.inp_lines[section_start:section_end]
        fields = getattr(self, section + '_fields')
        dtypes = getattr(self, section + '_dtypes')

        fields_by_catchtype = {'PLOWABLE' : fields[1:8], 'IMPERVIOUS' : fields[8:15], 
            'PERVIOUS' : fields[15:22], 'REMOVAL' : fields[22:29]}
        dtypes_by_catchtype = {'PLOWABLE' : dtypes[1:8], 'IMPERVIOUS' : dtypes[8:15], 
            'PERVIOUS' : dtypes[15:22], 'REMOVAL' : dtypes[22:29]}
        elements = []
        description = None
        past_header = False
        for i, line in enumerate(section_lines):
            if (re.match('^[\s]*\;', line) and not past_header) or re.match('^[\s]*$', line) or re.match('^[\s]*\[', line):
                continue

            if re.match('^[\s]*\;', line):
                past_header = True
                line = line.strip('\;')

                if description is None: description = line
                else: description = description + line
                continue
            else:
                past_header = True
                if re.search(';', line):
                    line, eol_desc = re.split('[ ;]*;', line, maxsplit=1)
                    if description:
                        description = description + eol_desc
                    else:
                        description = eol_desc

                line = line.split()

                if len(line) != 9:
                    if  len(line) == 8 and line[1] == 'REMOVAL':
                        line.append('')
                    else:
                        raise Exception('Error: swmmlib.get_SnowPacks: Unexpected line format encountered: ' + str(line))

                catchtype_colnum = 1
                current_catchtype = line[catchtype_colnum]

                current_fields = fields_by_catchtype[current_catchtype]
                current_dtypes = dtypes_by_catchtype[current_catchtype]

                current_parameters = line[(catchtype_colnum + 1):]
                current_parameters = [dtype(current_parameters[i]) for i, dtype in enumerate(current_dtypes)]

                name_colnum = 0
                current_name = line[name_colnum]

                has_element = False
                for element in elements:
                    if element['Name'] == current_name:
                        has_element = True
                        for i, field in enumerate(current_fields):
                            element[field] = current_parameters[i]
                        if element['Description'] and description:
                            element['Description'] = element['Description'] + description
                        elif description:
                            element['Description'] = description
                        description = None
                        break

                if not has_element:
                    element = dict(zip(fields, [None for i in range(len(fields))]))
                    element['Name'] = current_name
                    for i, field in enumerate(current_fields):
                        element[field] = current_parameters[i]
                    element['Description'] = description
                    elements.append(element)
                    description = None


        return elements

    def assign_Symbols(self, section, elements):
        symbols_elements = []
        symbols_fields = getattr(self, 'Symbols_fields')
        symbols_dtypes = getattr(self, section + '_dtypes')

        symbols_defaults = [None, None, None]
        if 'Symbols' in self.section_locations.keys():
            symbols_start = self.section_locations['Symbols'][0]
            symbols_end = self.section_locations['Symbols'][1]

            symbols_lines = self.inp_lines[symbols_start:symbols_end]

            description = None
            past_header = False
            for i, line in enumerate(symbols_lines):
                if (re.match('^[\s]*\;;', line) and not past_header) or re.match('^[\s]*$', line) or re.match('^[\s]*\[', line):
                    continue
                if re.match('^[\s]*\;', line):
                    past_header = True
                    line = line.strip('\;')
                    if description is None: description = line
                    else: description = description + line
                    continue
                else:
                    past_header = True
                    if re.search(';', line):
                        line, eol_desc = re.split('[ ;]*;', line, maxsplit=1)
                        if description:
                            description = description + eol_desc
                        else:
                            description = eol_desc

                    line = line.split()
                    if len(line) != len(symbols_fields):
                        raise Exception("Error: swmmlib.assign_Symbols: Unexpected line format encountered: " + str(line))
                    for j, value in enumerate(line):
                        if value is not None:
                            line[j] = symbols_dtypes[j](value)
                    params = dict(zip(symbols_fields, line))
                    params['CoordinateDescription'] = re.sub('\n$', '', description, count=1) if description else description
                    description = None
                    symbols_elements.append(params)

        fields = getattr(self, section + "_fields")
        symbols_fields = symbols_fields + ['CoordinateDescription']
        if len(symbols_elements) > 0:
            for i in xrange(len(elements)):
                name = elements[i][fields[0]]
                symbols_have_element = False
                for j in xrange(len(symbols_elements)):
                    symbols_name = symbols_elements[j][symbols_fields[0]]
                    if name == symbols_name:
                        for fieldname in symbols_fields[1:]:
                            elements[i][fieldname] = symbols_elements[j][fieldname]
                        symbols_have_element = True
                        break
                if not symbols_have_element:
                    for j, fieldname in enumerate(symbols_fields[1:]):
                        elements[i][fieldname] = symbols_defaults[j]
        else:
            for i in xrange(len(elements)):
                for j, field_name in enumerate(symbols_fields[1:]):
                    elements[i][field_name] = symbols_defaults[j]

        return elements

    ## Subcatchments
    def get_Subcatchments(self):
        section = 'Subcatchments'
        if section not in self.section_locations.keys():
            return []

        section_start = self.section_locations[section][0]
        section_end = self.section_locations[section][1]
        section_lines = self.inp_lines[section_start:section_end]
        fields = getattr(self, section + '_fields')
        dtypes = getattr(self, section + '_dtypes')

        elements = []
        description = None
        past_header = False
        for i, line in enumerate(section_lines):
            if (re.match('^[\s]*\;\;', line) and not past_header) or re.match('^[\s]*$', line) or re.match('^[\s]*\[', line):
                continue
            if re.match('^[\s]*\;', line):
                past_header = True
                line = line.strip('\;')
                if description is None: description = line
                else: description = description + line
                continue
            else:
                past_header = True
                if re.search(';', line):
                    line, eol_desc = re.split('[ ;]*;', line, maxsplit=1)
                    if description:
                        description = description + eol_desc
                    else:
                        description = eol_desc

                line = line.split()
                if len(line) < len(fields):
                    if len(line) == (len(fields) - 1):
                        line.append(None)
                    else:
                        raise Exception("Error: swmmlib: get_Subcatchments: Unexpected line format encountered." + str(line))

                for j, value in enumerate(line):
                    if value is not None:
                        line[j] = dtypes[j](value)
                params = dict(zip(fields, line))
                params['Description'] = re.sub('\n$', '', description, count = 1) if description is not None else None
                elements.append(params)
                description = None

        if len(elements) > 0:
            for subclass in getattr(self, section + '_subclasses'):
                elements = getattr(self, 'assign_' + subclass)(section, elements)
            
        return elements

    def assign_Subareas(self, section, elements):
        if 'Subareas' not in self.section_locations.keys():
            raise Exception("Error: SMMIO.assign_Subareas: Subcatchments loaded without subareas")
        else:
            subareas_start = self.section_locations['Subareas'][0]
            subareas_end = self.section_locations['Subareas'][1]

            subareas_elements = []
            subareas_lines = self.inp_lines[subareas_start:subareas_end]
            subareas_fields = getattr(self, 'Subareas_fields')
            subareas_dtypes = getattr(self, 'Subareas_dtypes')

            description = None
            description_name = 'SubareasDescription'
            past_header = False
            for i, line in enumerate(subareas_lines):
                if (re.match('^[\s]*\;\;', line) and not past_header) or re.match('^[\s]*$', line) \
                or re.match('^[\s]*\[', line):
                    continue
                if re.match('^[\s]*\;', line):
                    past_header = True
                    line = line.strip('\;')
                    if description is None: description = line
                    else: description = description + line
                    continue
                else:
                    past_header = True
                    if re.search('\;', line):
                        if re.search(';', line):
                            line, eol_desc = re.split('[ ;]*;', line, maxsplit=1)
                            if description:
                                description = description + eol_desc
                            else:
                                description = eol_desc

                    line = line.split()
                    if len(line) != len(subareas_fields):
                        if len(line) == (len(subareas_fields) - 1):
                            line.append(None)
                        else:
                            raise Exception("Error: swmmlib.assign_Subareas: Unexpected line format encountered: " + \
                                    str(line))
                    for j, value in enumerate(line):
                        if value is not None:
                            line[j] = subareas_dtypes[j](value)
                    params = dict(zip(subareas_fields, line))
                    params[description_name] = re.sub('\n$', '', description, count = 1) if description is not None else None
                    description = None
                    subareas_elements.append(params)

            if len(subareas_elements) == 0:
                raise Exception("Error: swmmlib.assign_Subareas: Subcatchments loaded without subareas")
            else:
                fields = getattr(self, "Subcatchments_fields")
                for i in xrange(len(elements)):
                    name = elements[i][fields[0]]
                    subareas_elements_have_element = False
                    for j in xrange(len(subareas_elements)):
                        subareas_name = subareas_elements[j][subareas_fields[0]]
                        if name == subareas_name:
                            for fieldname in subareas_fields[1:]:
                                elements[i][fieldname] = subareas_elements[j][fieldname]
                            elements[i][description_name] = subareas_elements[j][description_name]
                            subareas_elements_have_element = True
                            break
                    if not subareas_elements_have_element:
                        raise Exception("Error: swmmlib.assign_Subareas: No subarea record for subcatchment " + name)
        
                return elements

    def assign_Groundwater(self, section, elements):
        groundwater_elements = []
        groundwater_fields = getattr(self, 'Groundwater_fields')
        groundwater_dtypes = getattr(self, 'Groundwater_dtypes')
        groundwater_defaults = [None for i in xrange(len(groundwater_fields)-1)]

        if 'Groundwater' in self.section_locations.keys():
            groundwater_start = self.section_locations['Groundwater'][0]
            groundwater_end = self.section_locations['Groundwater'][1]

            groundwater_lines = self.inp_lines[groundwater_start:groundwater_end]

            description = None
            description_name = 'GWDescription'
            past_header = False
            for i, line in enumerate(groundwater_lines):
                if (re.match('^[\s]*\;\;', line) and not past_header) or re.match('^[\s]*$', line) or re.match('^[\s]*\[', line):
                    continue
                if re.match('^[\s]*\;', line):
                    past_header = True
                    line = line.strip('\;')
                    if description is None: description = line
                    else: description = description + line
                    continue
                else:
                    past_header = True
                    if re.search(';', line):
                        line, eol_desc = re.split('[ ;]*;', line, maxsplit=1)
                        if description:
                            description = description + eol_desc
                        else:
                            description = eol_desc
                    line = line.split()
                    if len(line) != len(groundwater_fields):
                        if len(line) == (len(groundwater_fields) - 1):
                            line.append(None)
                        else:
                            raise Exception("Error: swmmlib.assign_Groundwater: Unexpected line format encountered: " + str(line))
                    for j, value in enumerate(line):
                        if value is not None:
                            line[j] = groundwater_dtypes[j](value)
                    params = dict(zip(groundwater_fields, line))
                    params[description_name] = re.sub('\n$', '', description, count = 1) if description is not None else None
                    description = None
                    groundwater_elements.append(params)

        fields = getattr(self, 'Subcatchments_fields')
        if len(groundwater_elements) > 0:
            for i in xrange(len(elements)):
                name = elements[i][fields[0]]
                groundwater_elements_have_element = False
                for j in xrange(len(groundwater_elements)):
                    groundwater_name = groundwater_elements[j][groundwater_fields[0]]
                    if name == groundwater_name:
                        for fieldname in groundwater_fields[1:]:
                            elements[i][fieldname] = groundwater_elements[j][fieldname]
                        elements[i][description_name] = groundwater_elements[j][description_name]
                        groundwater_elements_have_element = True
                        break
                if not groundwater_elements_have_element:
                    for j, fieldname in enumerate(groundwater_fields[1:]):
                        elements[i][fieldname] = groundwater_defaults[j]
        else:
            for i in xrange(len(elements)):
                for j, field_name in enumerate(groundwater_fields[1:]):
                    elements[i][field_name] = groundwater_defaults[j]
        
        return elements

    def assign_Infiltration(self, section, elements):
        if 'Infiltration' not in self.section_locations.keys():
            raise Exception("Error: swmmlib.assign_Infiltration: Subcatchments loaded without infiltration")
        else:
            infiltration_start = self.section_locations['Infiltration'][0]
            infiltration_end = self.section_locations['Infiltration'][1]

            infiltration_elements = []
            infiltration_lines = self.inp_lines[infiltration_start:infiltration_end]

            options = self.get_Options()
            if len(options) == 0:
                raise Exception("Error: swmmlib.assign_Infiltration: INP file does not include [OPTIONS], can't determine infiltration method")
            options = options[0] # get options returns a list of the options dict
            infil_method = options['INFILTRATION']
            if infil_method == 'HORTON': 
                primary_fields = getattr(self, 'Infiltration2_fields')
                primary_dtypes = getattr(self, 'Infiltration2_dtypes')
                secondary_fields = getattr(self, 'Infiltration1_fields')[1:]
            elif infil_method == 'GREEN_AMPT':
                primary_fields = getattr(self, 'Infiltration1_fields')
                primary_dtypes = getattr(self, 'Infiltration1_dtypes')
                secondary_fields = getattr(self, 'Infiltration2_fields')[1:]
            else:
                raise Exception("Error: swmmlib.assign_Infiltration: Unrecogized infiltration method: " + str(infil_method))

            description = None
            description_name = 'InfiltrationDescription'
            past_header = False
            for i, line in enumerate(infiltration_lines):
                if (re.match('^[\s]*\;\;', line) and not past_header) or re.match('^[\s]*$', line) or re.match('^[\s]*\[', line):
                    continue
                if re.match('^[\s]*\;', line):
                    past_header = True
                    line = line.strip('\;')
                    if description is None: description = line
                    else: description = description + line
                    continue
                else:
                    past_header = True
                    if re.search(';', line):
                        line, eol_desc = re.split('[ ;]*;', line, maxsplit=1)
                        if description:
                            description = description + eol_desc
                        else:
                            description = eol_desc
                    line = line.split()
                    if len(line) != len(primary_fields):
                        raise Exception("Error: swmmlib.assign_Infiltration: Unexpected line format encountered: " + str(line))
                    for j, value in enumerate(line):
                        if value is not None:
                            line[j] = primary_dtypes[j](value)
                    params = dict(zip(primary_fields, line))
                    for field in secondary_fields:
                        params[field] = None
                    params[description_name] = re.sub('\n$', '', description, count = 1) if description is not None else None
                    description = None
                    infiltration_elements.append(params)

            if len(infiltration_elements) == 0:
                raise Exception("Error: swmmlib.assign_Infiltration: Subcatchments loaded without infiltration")
            else:
                fields = getattr(self, "Subcatchments_fields")
                for i in xrange(len(elements)):
                    name = elements[i][fields[0]]
                    infiltration_elements_have_element = False
                    for j in xrange(len(infiltration_elements)):
                        infiltration_name = infiltration_elements[j][primary_fields[0]]
                        if name == infiltration_name:
                            for fieldname in primary_fields[1:]:
                                elements[i][fieldname] = infiltration_elements[j][fieldname]
                            for fieldname in secondary_fields:
                                elements[i][fieldname] = infiltration_elements[j][fieldname]
                            elements[i][description_name] = infiltration_elements[j][description_name]
                            infiltration_elements_have_element = True
                            break
                    if not infiltration_elements_have_element:
                        raise Exception("Error: swmmlib.assign_Infiltration: No infiltration record for subcatchment " + name)
                return elements

    def get_Notes(self):
        section = 'Notes'
        if section not in self.section_locations.keys():
            return []

        section_start = self.section_locations[section][0]
        section_end = self.section_locations[section][1]
        if (section_end - section_start) == 1:
            return []

        section_lines = self.inp_lines[section_start:section_end]

        notes = {'NotesText' : ''}
        blanks = ''
        for i, line in enumerate(section_lines):
            if i == 0:
                continue
            if re.match('[\s]*\n', line):
                blanks += line
            else:
                if blanks:
                    line = blanks + line
                    blanks = ''
                notes['NotesText'] += line

        return [notes]

    def get_Options(self):
        section = 'Options'
        if section not in self.section_locations.keys():
            return []

        section_start = self.section_locations[section][0]
        section_end = self.section_locations[section][1]
        section_lines = self.inp_lines[section_start:section_end]

        fields = getattr(self, section + '_fields')
        dtypes = getattr(self, section + '_dtypes')

        options = {} 
        for i, line in enumerate(section_lines):
            if re.match('^[\s]*\;', line) or re.match('^[\s]*$', line) or re.match('^[\s]*\[', line):
                continue
            else:
                line = line.split()
                if len(line) != 2:
                    raise Exception("Error: swmmlib: get_Options: Unexpected line format encountered: " + str(line))
                param = line[0]
                value = line[1]
                options[param] = dtypes[fields.index(param)](value)

        return [options]

    def get_Report(self):
        section = 'Report'
        if section not in self.section_locations.keys():
            return []

        section_start = self.section_locations[section][0]
        section_end = self.section_locations[section][1]
        section_lines = self.inp_lines[section_start:section_end]

        fields = getattr(self, section + '_fields')
        dtypes = getattr(self, section + '_dtypes')

        report = {} 
        links = []
        nodes = []
        catchments = []
        for i, line in enumerate(section_lines):
            if re.match('^[\s]*\;', line) or re.match('^[\s]*$', line) or re.match('^[\s]*\[', line):
                continue
            else:
                line = line.split(None, 1)
                if len(line) != 2:
                    raise Exception("Error: swmmlib: get_Report: Unexpected line format encountered: " + str(line))
                param = line[0].strip().upper()
                value = line[1].strip()
                link_pat = re.compile('^link', re.IGNORECASE)
                node_pat = re.compile('^node', re.IGNORECASE)
                catch_pat = re.compile('^subcatchments', re.IGNORECASE)

                if re.search(link_pat, param):
                    links.extend(value.split())
                elif re.search(node_pat, param):
                    nodes.extend(value.split())
                elif re.search(catch_pat, param):
                    catchments.extend(value.split())
                else:
                    report[param] = dtypes[fields.index(param)](value)

        report['LINKS'] = ' '.join(links) if links else None
        report['NODES'] = ' '.join(nodes) if nodes else None
        report['SUBCATCHMENTS'] = ' '.join(catchments) if catchments else None
        return [report]

    def get_Maps(self):
        section = 'Maps'
        if section not in self.section_locations.keys():
            return []

        section_start = self.section_locations[section][0]
        section_end = self.section_locations[section][1]
        section_lines = self.inp_lines[section_start:section_end]

        map_opts = {}
        for i, line in enumerate(section_lines):
            if re.match('^[\s]*\;', line) or re.match('^[\s]*$', line) or re.match('^[\s]*\[', line):
                continue
            else:
                line = line.split(None, 1)
                if len(line) != 2:
                    raise Exception("Error: swmmlib.get_Maps: Unexpected line format encountered: " + str(line))
                elif line[0] == 'DIMENSIONS':
                    dims = line[1].split()
                    if len(dims) != 4:
                        raise Exception("Error: swmmlib.get_Maps: Unexpected line format encountered: " + str(line))
                    else:
                        dims = [float(dim) for dim in dims]
                        map_opts['LLXCoordinate'] = dims[0]
                        map_opts['LLYCoordinate'] = dims[1]
                        map_opts['URXCoordinate'] = dims[2]
                        map_opts['URYCoordinate'] = dims[3]
                elif line[0] == 'Units':
                    map_opts['Units'] = line[1].strip()
                else:
                    raise Exception("Error: swmmlib.get_Maps: Unexpected line format encountered: " + str(line))

        return [map_opts]

    def get_Evaporation(self):
        section = 'Evaporation'
        if section not in self.section_locations.keys():
            return []

        section_start = self.section_locations[section][0]
        section_end = self.section_locations[section][1]
        section_lines = self.inp_lines[section_start:section_end]

        evaporation = {'Recovery' : None}
        for i, line in enumerate(section_lines):
            if re.match('^[\s]*\;', line) or re.match('^[\s]*$', line) or re.match('^[\s]*\[', line):
                continue
            else:
                line = line.split()
                marker = line[0]

                if marker in ('CONSTANT', 'TIMESERIES', 'FILE', 'TEMPERATURE', 'MONTHLY'):
                    evaporation['Type'] = marker
                    parameters = ' '.join(line[1:])

                    if len(parameters) == 0:
                        parameters = None

                    evaporation['Parameters'] = parameters
                elif marker in ('RECOVERY', 'DRY_ONLY'):
                    if len(line) != 2:
                        raise Exception('Error: swmmlib.get_Evaporation: Unexpected line format encountered: ' + str(line))
                    else:
                        if marker == 'RECOVERY':
                            field = 'Recovery'
                        elif marker == 'DRY_ONLY':
                            field = 'DryOnly'

                        evaporation[field] = line[1]
                else:
                    raise Exception('Error: swmmlib.get_Evaporation: Unexpected line type encountered: ' + str(line))

        return [evaporation]

    def get_PatternMultipliers(self):
        section = 'PatternMultipliers'
        if section not in self.section_locations.keys():
            return []

        section_start = self.section_locations[section][0]
        section_end = self.section_locations[section][1]
        section_lines = self.inp_lines[section_start:section_end]

        elements = []
        new_pattern = True
        description = None
        past_header = False
        pattern_descriptions = {}
        for i, line in enumerate(section_lines):
            if (re.match('^[\s]*\;\;', line) and not past_header) or re.match('^[\s]*$', line) or re.match('^[\s]*\[', line):
                continue
            elif re.match('^[\s]*\;', line):
                past_header = True
                line = line.strip('\;')
                if description is None: description = line
                else: description = description + line
                continue
            else:
                past_header = True
                if re.search(';', line):
                    line, eol_desc = re.split('[ ;]*;', line, maxsplit=1)
                    if description:
                        description = description + eol_desc
                    else:
                        description = eol_desc

                line = line.split()
                try:
                    dummy = float(line[1])
                except:
                    new_pattern = True
                else:
                    new_pattern = False

                if new_pattern:
                    pattern = line[0]
                    pattern_descriptions[pattern] = description
                    pat_type = line[1]
                    current_ordinal = 1
                    for multiplier in line[2:]:
                        name = ':'.join([pattern, pat_type, str(current_ordinal)])
                        params = {'Name'        : name, 
                                  'Pattern'     : pattern,
                                  'Type'        : pat_type,
                                  'Ordinal'     : current_ordinal,
                                  'Multiplier'  : float(multiplier)}
                        elements.append(params)
                        if current_ordinal == 1:
                            description = None # description only follows first multiplier, so reset description
                        current_ordinal += 1
                else:
                    if description:
                        current_desc = pattern_descriptions[pattern] 
                        pattern_descriptions[pattern] = current_desc + description if current_desc else description
                    for multiplier in line[1:]:
                        name = ':'.join([pattern, pat_type, str(current_ordinal)])
                        params = {'Name'        : name, 
                                  'Pattern'     : pattern,
                                  'Type'        : pat_type,
                                  'Ordinal'     : current_ordinal,
                                  'Multiplier'  : float(multiplier)}
                        elements.append(params)
                        current_ordinal += 1

                description = None

        for element in elements:
            desc = pattern_descriptions[element['Pattern']]
            element['Description'] = re.sub('\n$', '', desc, count = 1) if desc else None

        return elements

    def get_Files(self):
        section = 'Files'
        if section not in self.section_locations.keys():
            return []

        section_start = self.section_locations[section][0]
        section_end = self.section_locations[section][1]
        section_lines = self.inp_lines[section_start:section_end]

        section_lines = self.inp_lines[section_start:section_end]
        fields = getattr(self, section + '_fields')
        dtypes = getattr(self, section + '_dtypes')

        elements = []
        current_file_num = 1
        for i, line in enumerate(section_lines):
            if re.match('^[\s]*\;', line) or re.match('^[\s]*$', line) or re.match('^[\s]*\[', line):
                continue
            else:
                line = line.split(None, 2)
                if len(line) != len(fields):
                    raise Exception("Error: swmmlib: get_Files: Unexpected line format encountered: " + str(line))
                for j, value in enumerate(line):
                    if value is not None:
                        line[j] = dtypes[j](value)
                params = dict(zip(fields, line))
                name = ':'.join([params['Usage'], params['FileType'], str(current_file_num)])
                params['Name'] = name
                params['Ordinal'] = current_file_num
                if params['Usage'] == 'USE' and self.require_support_files:
                    fpath = os.path.join(os.path.dirname(self.inp_path), params['FileName'].strip(' \n\t"'))
                    if not os.path.exists(fpath):
                        raise Exception("Can't find support file '" + fpath + "' referenced in [FILES]")
                    else:
                        params['FileName'] = '"' + os.path.basename(fpath) + '"'
                        with open(fpath, 'rb') as f:
                            fcontents = f.read()
                        fbuffer = buffer(fcontents)
                        md5 = hashlib.md5(fcontents).hexdigest()
                        params['FileMD5'] = md5
                        self.files[md5] = fbuffer
                else:
                    params['FileName'] = params['FileName'].strip()
                    params['FileMD5'] = None
                elements.append(params)
                current_file_num += 1

        return elements

    def get_Aquifers(self):
        section = 'Aquifers'
        if section not in self.section_locations.keys():
            return []

        section_start = self.section_locations[section][0]
        section_end = self.section_locations[section][1]
        section_lines = self.inp_lines[section_start:section_end]
        fields = getattr(self, section + '_fields')
        dtypes = getattr(self, section + '_dtypes')

        elements = []
        description = None
        past_header = False
        for i, line in enumerate(section_lines):
            if (re.match('^[\s]*\;\;', line) and not past_header) or re.match('^[\s]*$', line) or re.match('^[\s]*\[', line):
                continue
            if re.match('^[\s]*\;', line):
                past_header = True
                line = line.strip('\;')
                if description is None: description = line
                else: description = description + line
                continue
            else:
                past_header = True
                if re.search(';', line):
                    line, eol_desc = re.split('[ ;]*;', line, maxsplit=1)
                    if description:
                        description = description + eol_desc
                    else:
                        description = eol_desc
                line = line.split()
                if len(line) != len(fields):
                    raise Exception("Error: swmmlib: get_Aquifers: Unexpected line format encountered: " + str(line))
                for j, value in enumerate(line):
                    if value is not None:
                        line[j] = dtypes[j](value)
                params = dict(zip(fields, line))
                params['Description'] = re.sub('\n$', '', description, count = 1) if description is not None else None
                elements.append(params)
                description = None

        return elements

    def get_PolygonPoints(self):
        section = 'PolygonPoints'
        if section not in self.section_locations.keys():
            return []

        section_start = self.section_locations[section][0]
        section_end = self.section_locations[section][1]
        section_lines = self.inp_lines[section_start:section_end]
        fields = getattr(self, section + '_fields')
        dtypes = getattr(self, section + '_dtypes')

        elements = []
        prev_catch = ""
        past_header = False
        description = None
        for i, line in enumerate(section_lines):
            if (re.match('^[\s]*\;;', line) and not past_header) or re.match('^[\s]*$', line) or re.match('^[\s]*\[', line):
                continue

            if re.match('^[\s]*\;', line):
                past_header = True
                line = line.strip('\;')
                if description is None: description = line
                else: description = description + line
                continue
            else:
                past_header = True
                if re.search(';', line):
                    line, eol_desc = re.split('[ ;]*;', line, maxsplit=1)
                    if description:
                        description = description + eol_desc
                    else:
                        description = eol_desc
                line = line.split()
                if len(line) != len(fields):
                    raise Exception("Error: swmmr.get_Polygons: Unexpected line format encountered: " + str(line))

                for j, value in enumerate(line):
                    if value is not None:
                        line[j] = dtypes[j](value)
                params = dict(zip(fields, line))
                current_catch = params['Subcatchment']
                if current_catch != prev_catch:
                    coord_ordinal = 1
                else:
                    coord_ordinal = coord_ordinal + 1
                name = ':'.join([params['Subcatchment'], str(coord_ordinal)])
                params['Ordinal'] = coord_ordinal
                params['Name'] = name
                params['Description'] = re.sub('\n$', '', description, count=1) if description else description
                description = None
                prev_catch = current_catch
                elements.append(params)

        return elements

    # Hydraulics
    ## Nodes
    def get_Junctions(self):
        section = 'Junctions'
        if section not in self.section_locations.keys():
            return []

        section_start = self.section_locations[section][0]
        section_end = self.section_locations[section][1]
        section_lines = self.inp_lines[section_start:section_end]
        fields = getattr(self, section + '_fields')
        dtypes = getattr(self, section + '_dtypes')

        elements = []
        description = None
        past_header = False
        for i, line in enumerate(section_lines):
            if (re.match('^[\s]*\;\;', line) and not past_header) or re.match('^[\s]*$', line) or re.match('^[\s]*\[', line):
                continue
            if re.match('^[\s]*\;', line):
                past_header = True
                line = line.strip('\;')
                if description is None: description = line
                else: description = description + line
                continue
            else:
                past_header = True
                if re.search(';', line):
                    line, eol_desc = re.split('[ ;]*;', line, maxsplit=1)
                    if description:
                        description = description + eol_desc
                    else:
                        description = eol_desc

                line = line.split()
                if len(line) != len(fields):
                    raise Exception("Error: swmmlib.get_Junctions: Unexpected line format encountered: " + str(line))
                for j, value in enumerate(line):
                    if value is not None:
                        line[j] = dtypes[j](value)
                params = dict(zip(fields, line))
                params['Description'] = re.sub('\n$', '', description, count = 1) if description is not None else None
                elements.append(params)
                description = None

        if len(elements) > 0:
            for subclass in getattr(self, section + '_subclasses'):
                elements = getattr(self, 'assign_' + subclass)(section, elements)

        return elements

    def get_Outfalls(self):
        section = 'Outfalls'
        if section not in self.section_locations.keys():
            return []

        section_start = self.section_locations[section][0]
        section_end = self.section_locations[section][1]
        section_lines = self.inp_lines[section_start:section_end]
        fields = getattr(self, section + '_fields')
        dtypes = getattr(self, section + '_dtypes')

        elements = []
        description = None
        past_header = False
        for i, line in enumerate(section_lines):
            if (re.match('^[\s]*\;\;', line) and not past_header) or re.match('^[\s]*$', line) or re.match('^[\s]*\[', line):
                continue
            if re.match('^[\s]*\;', line):
                past_header = True
                line = line.strip('\;')
                if description is None: description = line
                else: description = description + line
                continue
            else:
                past_header = True
                if re.search(';', line):
                    line, eol_desc = re.split('[ ;]*;', line, maxsplit=1)
                    if description:
                        description = description + eol_desc
                    else:
                        description = eol_desc

                line = line.split()
                if len(line) < len(fields):
                    if len(line) == (len(fields) - 1):
                        line.insert(3, None)
                    else:
                        raise Exception("Error: swmmlib.get_Outfalls: Unexpected line format encountered: " + str(line))

                for j, value in enumerate(line):
                    if value is not None:
                        line[j] = dtypes[j](value)
                params = dict(zip(fields, line))
                params['Description'] = re.sub('\n$', '', description, count = 1) if description is not None else None
                elements.append(params)
                description = None

        if len(elements) > 0:
            for subclass in getattr(self, section + '_subclasses'):
                elements = getattr(self, 'assign_' + subclass)(section, elements)

        return elements

    def get_Dividers(self):
        section = 'Dividers'
        if section not in self.section_locations.keys():
            return []

        section_start = self.section_locations[
                section][0]
        section_end = self.section_locations[section][1]
        section_lines = self.inp_lines[section_start:section_end]
        fields = getattr(self, section + '_fields')
        dtypes = getattr(self, section + '_dtypes')

        elements = []
        description = None
        field_lengths = set([len(fields)-4,len(fields)-2,len(fields)-5])
        past_header = False
        for i, line in enumerate(section_lines):
            if (re.match('^[\s]*\;\;', line) and not past_header) or re.match('^[\s]*$', line) or re.match('^[\s]*\[', line):
                continue
            if re.match('^[\s]*\;', line):
                past_header = True
                line = line.strip('\;')
                if description is None: description = line
                else: description = description + line
                continue
            else:
                past_header = True
                if re.search(';', line):
                    line, eol_desc = re.split('[ ;]*;', line, maxsplit=1)
                    if description:
                        description = description + eol_desc
                    else:
                        description = eol_desc
                line = line.split()

                if line[3] == 'OVERFLOW' and len(line) == len(fields) - 5:
                    line = line[0:4] + [None]*5 + line[4:]
                elif line[3] == 'WEIR' and len(line) == len(fields) - 2:
                    line = line[0:4] + [None]*2 + line[4:]
                elif ( line[3] == 'CUTOFF' or line[3] == 'TABULAR' ) and len(line) == len(fields) - 4:
                    if line[3] == 'CUTOFF':
                        line = line[0:4] + line[4:5] + [None]*4 + line[5:]
                    else:
                        line = line[0:4] + [None] + line[4:5] + [None]*3 + line[5:]
                else:
                    raise Exception("Error: swmmlib.get_Dividers: Unexpected line format encountered: " + str(line))

                for j, value in enumerate(line):
                    if value is not None:
                        line[j] = dtypes[j](value)
                params = dict(zip(fields, line))
                params['Description'] = re.sub('\n$', '', description, count = 1) if description is not None else None
                elements.append(params)
                description = None

        if len(elements) > 0:
            for subclass in getattr(self, section + '_subclasses'):
                elements = getattr(self, 'assign_' + subclass)(section, elements)

        return elements



    def get_Storage(self):
        section = 'Storage'
        if section not in self.section_locations.keys():
            return []

        section_start = self.section_locations[section][0]
        section_end = self.section_locations[section][1]
        section_lines = self.inp_lines[section_start:section_end]
        fields = getattr(self, section + '_fields')
        dtypes = getattr(self, section + '_dtypes')

        elements = []
        description = None
        past_header = False
        for i, line in enumerate(section_lines):
            if (re.match('^[\s]*\;\;', line) and not past_header) or re.match('^[\s]*$', line) or re.match('^[\s]*\[', line):
                continue
            if re.match('^[\s]*\;', line):
                past_header = True
                line = line.strip('\;')
                if description is None: description = line
                else: description = description + line
                continue
            else:
                past_header = True
                if re.search(';', line):
                    line, eol_desc = re.split('[ ;]*;', line, maxsplit=1)
                    if description:
                        description = description + eol_desc
                    else:
                        description = eol_desc

                line = line.split()
                storage_curve_index = fields.index('StorageCurve')
                curve_marker = line[storage_curve_index] # should be 'FUNCTIONAL' or 'TABULAR'
                if curve_marker == 'TABULAR':
                    none_fields = ['CurveCoeff', 'CurveExponent', 'CurveConstant']
                elif curve_marker == 'FUNCTIONAL':
                    none_fields = ['CurveName']
                else:
                    raise Exception('Error: swmmlib.get_Storage: Unexpected storage curve type encountered: ' + str(line))

                min_none_field_count = len(none_fields)
                insert_indexes = [fields.index(fieldname) for fieldname in none_fields]

                if (len(line) + min_none_field_count) <= len(fields):
                    for i in insert_indexes:
                        line.insert(i, None)
                else:
                    raise Exception('Error: swmmlib.get_Storage: Record has more parameters than expected: ' + str(line))

                if (len(line) != len(fields)) and ((len(line) + 3) == len(fields)):
                    line.extend([None for i in xrange(3)])
                elif len(line) != len(fields):
                    raise Exception('Error: swmmlib.get_Storage: Unexpected line format encountered: ' + str(line))

                for j, value in enumerate(line):
                    if value is not None:
                        line[j] = dtypes[j](value)

                params = dict(zip(fields, line))
                params['Description'] = re.sub('\n$', '', description, count = 1) if description is not None else None
                elements.append(params)
                description = None

        if len(elements) > 0:
            for subclass in getattr(self, section + '_subclasses'):
                elements = getattr(self, 'assign_' + subclass)(section, elements)

        return elements

    def assign_RDII(self, section, elements):
        rdii_elements = []
        rdii_fields = getattr(self, 'RDII_fields')
        rdii_dtypes = getattr(self, 'RDII_dtypes')
        rdii_defaults = [None, None]

        if 'RDII' in self.section_locations.keys():
            rdii_start = self.section_locations['RDII'][0]
            rdii_end = self.section_locations['RDII'][1]

            rdii_lines = self.inp_lines[rdii_start:rdii_end]

            description = None
            description_name = 'RDIIDescription'
            past_header = False
            for i, line in enumerate(rdii_lines):
                if (re.match('^[\s]*\;\;', line) and not past_header) or re.match('^[\s]*$', line) or re.match('^[\s]*\[', line):
                    continue
                if re.match('^[\s]*\;', line):
                    past_header = True
                    line = line.strip('\;')
                    if description is None: description = line
                    else: description = description + line
                    continue
                else:
                    past_header = True
                    if re.search(';', line):
                        line, eol_desc = re.split('[ ;]*;', line, maxsplit=1)
                        if description:
                            description = description + eol_desc
                        else:
                            description = eol_desc
                    line = line.split()
                    if len(line) != len(rdii_fields):
                        raise Exception("Error: swmmlib.assign_RDII: Unexpected line format encountered: " + str(line))
                    for j, value in enumerate(line):
                        if value is not None:
                            line[j] = rdii_dtypes[j](value)
                    params = dict(zip(rdii_fields, line))
                    params[description_name] = re.sub('\n$', '', description, count = 1) if description is not None else None
                    description = None
                    rdii_elements.append(params)

        fields = getattr(self, section + "_fields")
        if len(rdii_elements) > 0:
            for i in xrange(len(elements)):
                name = elements[i][fields[0]]
                rdii_have_element = False
                for j in xrange(len(rdii_elements)):
                    rdii_name = rdii_elements[j][rdii_fields[0]]
                    if name == rdii_name:
                        for fieldname in rdii_fields[1:]:
                            elements[i][fieldname] = rdii_elements[j][fieldname]
                        rdii_have_element = True
                        elements[i][description_name] = rdii_elements[j][description_name]
                        break
                if not rdii_have_element:
                    for j, fieldname in enumerate(rdii_fields[1:]):
                        elements[i][fieldname] = rdii_defaults[j]
        else:
            for i in xrange(len(elements)):
                for j, field_name in enumerate(rdii_fields[1:]):
                    elements[i][field_name] = rdii_defaults[j]

        return elements

    def get_Coordinates(self):
        coors_elements = []
        coors_fields = getattr(self, 'Coordinates_fields')
        coors_dtypes = getattr(self, 'Coordinates_dtypes')
        coors_defaults = [None, None]

        if 'Coordinates' in self.section_locations.keys():
            coors_start = self.section_locations['Coordinates'][0]
            coors_end = self.section_locations['Coordinates'][1]

            coors_lines = self.inp_lines[coors_start:coors_end]

            past_header = False
            description = None
            for i, line in enumerate(coors_lines):
                if (re.match('^[\s]*\;',line) and not past_header) or re.match('^[\s]*$',line) or re.match('^[\s]*\[', line):
                    continue
                if re.match('^[\s]*\;', line):
                    past_header = True
                    line = line.strip('\;')
                    if description is None: description = line
                    else: description = description + line
                    continue
                else:
                    past_header = True
                    if re.search(';', line):
                        line, eol_desc = re.split('[ ;]*;', line, maxsplit=1)
                        if description:
                            description = description + eol_desc
                        else:
                            description = eol_desc

                    line = line.split()
                    if len(line) != len(coors_fields):
                        raise Exception("Error: swmmlib.assign_Coordinates: Unexpected line format encountered: " + str(line))
                    for j, value in enumerate(line):
                        if value is not None:
                            line[j] = coors_dtypes[j](value)
                    params = dict(zip(coors_fields, line))
                    params['CoordinateDescription'] = re.sub('\n$', '', description, count=1) if description else description
                    description = None
                    coors_elements.append(params)

            return coors_elements

    def assign_Coordinates(self, section, elements):
        coors_elements = self.get_Coordinates()
        fields = getattr(self, section + '_fields')
        coors_fields = getattr(self, 'Coordinates_fields')
        coors_fields = coors_fields + ['CoordinateDescription']
        coors_defaults = [None, None, None]
        if coors_elements:
            for i in xrange(len(elements)):
                name = elements[i][fields[0]]
                coors_have_element = False
                for j in xrange(len(coors_elements)):
                    coors_name = coors_elements[j][coors_fields[0]]
                    if name == coors_name:
                        for fieldname in coors_fields[1:]:
                            elements[i][fieldname] = coors_elements[j][fieldname]
                        coors_have_element = True
                        break
                if not coors_have_element:
                    for j, fieldname in enumerate(coors_fields[1:]):
                        elements[i][fieldname] = coors_defaults[j]
        else:
            for i in xrange(len(elements)):
                for j, field_name in enumerate(coors_fields[1:]):
                    elements[i][field_name] = coors_defaults[j]

        return elements

    def get_Vertices(self):
        section = 'Vertices'
        if section not in self.section_locations.keys():
            return []

        section_start = self.section_locations[section][0]
        section_end = self.section_locations[section][1]
        section_lines = self.inp_lines[section_start:section_end]
        fields = getattr(self, section + '_fields')
        dtypes = getattr(self, section + '_dtypes')

        elements = []
        prev_link = ""
        past_header = False
        description = None
        for i, line in enumerate(section_lines):
            if (re.match('^[\s]*\;;', line) and not past_header) or re.match('^[\s]*$', line) or re.match('^[\s]*\[', line):
                continue
            if re.match('^[\s]*\;', line):
                past_header = True
                line = line.strip('\;')
                if description is None: description = line
                else: description = description + line
                continue
            else:
                past_header = True
                if re.search(';', line):
                    line, eol_desc = re.split('[ ;]*;', line, maxsplit=1)
                    if description:
                        description = description + eol_desc
                    else:
                        description = eol_desc

                line = line.split()
                if len(line) != len(fields):
                    raise Exception("Error: swmmlib.get_Vertices: Unexpected line format encountered: " + str(line))

                for j, value in enumerate(line):
                    if value is not None:
                        line[j] = dtypes[j](value)

                params = dict(zip(fields, line))
                current_link = params['Link']
                if current_link != prev_link:
                    coord_ordinal = 1
                else:
                    coord_ordinal = coord_ordinal + 1
                name = ':'.join([params['Link'], str(coord_ordinal)])
                params['Name'] = name
                params['Ordinal'] = coord_ordinal
                params['Description'] = re.sub('\n$', '', description, count=1) if description else description
                description = None
                prev_link = current_link
                elements.append(params)

        return elements

    def get_Inflows(self):
        section = 'Inflows'
        if section not in self.section_locations.keys():
            return []

        section_start = self.section_locations[section][0]
        section_end = self.section_locations[section][1]
        section_lines = self.inp_lines[section_start:section_end]
        fields = getattr(self, section + '_fields')
        dtypes = getattr(self, section + '_dtypes')

        elements = []
        description = None
        past_header = False
        for i, line in enumerate(section_lines):
            if (re.match('^[\s]*\;\;', line) and not past_header) or re.match('^[\s]*$', line) or re.match('^[\s]*\[', line):
                continue
            if re.match('^[\s]*\;', line):
                past_header = True
                line = line.strip('\;')
                if description is None: description = line
                else: description = description + line
                continue
            else:
                past_header = True
                if re.search(';', line):
                    line, eol_desc = re.split('[ ;]*;', line, maxsplit=1)
                    if description:
                        description = description + eol_desc
                    else:
                        description = eol_desc

                line = line.split()
                if len(line) < len(fields):
                    if len(line) == (len(fields) - 1):
                        line.append(None)
                    elif len(line) == (len(fields) - 2):
                        line.extend([None, None])
                    else:
                        raise Exception("Error: swmmlib.get_Inflows: Unexpected line format encountered: " + str(line))
                for j, value in enumerate(line):
                    if value is not None:
                        value = value.strip()
                        line[j] = dtypes[j](value)
                params = dict(zip(fields, line))
                params['InflowsDescription'] = re.sub('\n$', '', description, count = 1) if description is not None else None
                description = None
                elements.append(params)

        return elements

    def get_DWF(self):
        section = 'DWF'
        if section not in self.section_locations.keys():
            return []

        section_start = self.section_locations[section][0]
        section_end = self.section_locations[section][1]
        section_lines = self.inp_lines[section_start:section_end]
        fields = getattr(self, section + '_fields')
        dtypes = getattr(self, section + '_dtypes')

        elements = []
        description = None
        past_header = False
        for i, line in enumerate(section_lines):
            if (re.match('^[\s]*\;\;', line) and not past_header) or re.match('^[\s]*$', line) or re.match('^[\s]*\[', line):
                continue
            if re.match('^[\s]*\;', line):
                past_header = True
                line = line.strip('\;')
                if description is None: description = line
                else: description = description + line
                continue
            else:
                past_header = True
                if re.search(';', line):
                    line, eol_desc = re.split('[ ;]*;', line, maxsplit=1)
                    if description:
                        description = description + eol_desc
                    else:
                        description = eol_desc

                line = line.split(None, 3)
                if len(line) < len(fields):
                    if len(line) == (len(fields) - 1):
                        line.append(None)
                    else:
                        raise Exception("Error: swmmlib.get_DWF: Unexpected line format encountered: " + str(line))
                for j, value in enumerate(line):
                    if value is not None:
                        value = value.strip()
                        line[j] = dtypes[j](value)
                params = dict(zip(fields, line))
                params['DWFDescription'] = re.sub('\n$', '', description, count = 1) if description is not None else None
                description = None
                elements.append(params)

        return elements

    def get_NodeInflows(self):
        has_inflows = 'Inflows' in self.section_locations.keys()
        has_dwf = 'DWF' in self.section_locations.keys()

        if has_inflows:
            inflows = self.get_Inflows()
        if has_dwf:
            dwfs = self.get_DWF()

        if has_inflows and not has_dwf:
            for row in inflows:
                for field in self.DWF_fields[2:]:
                    row[field] = None
            final = inflows
        elif has_dwf and not has_inflows:
            for row in dwfs:
                for field in self.Inflows_fields[2:]:
                    row[field] = None
            final = dwfs
        else:
            for inflow in inflows:
                inflow_node = inflow[self.Inflows_fields[0]]
                inflow_param =  inflow[self.Inflows_fields[1]]
                dwf_has_inflow = False
                for dwf in dwfs:
                    dwf_node = dwf[self.DWF_fields[0]]
                    dwf_param = dwf[self.DWF_fields[1]]
                    if inflow_node == dwf_node and inflow_param == dwf_param:
                        for field in self.DWF_fields[2:]:
                            inflow[field] = dwf[field]
                        dwf_has_inflow = True
                        break
                if not dwf_has_inflow:
                    for field in self.DWF_fields[2:]:
                        inflow[field] = None

            for dwf in dwfs:
                dwf_node = dwf[self.DWF_fields[0]]
                dwf_param = dwf[self.DWF_fields[1]]
                inflow_has_dwf = False
                for inflow in inflows:
                    inflow_node = inflow[self.Inflows_fields[0]]
                    inflow_param = inflow[self.Inflows_fields[1]]
                    if dwf_node == inflow_node and dwf_param == inflow_param:
                        inflow_has_dwf = True
                        break
                if not inflow_has_dwf:
                    for field in self.Inflows_fields[2:]:
                        dwf[field] = None
                    inflows.append(dwf)

            final = inflows

        for row in final:
            row['Name'] = row['Node'] + ':' + row['Parameter']

        return final

    def get_Profiles(self):
        section = 'Profiles'

        if section not in self.section_locations.keys():
            return []

        section_start = self.section_locations[section][0]
        section_end = self.section_locations[section][1]
        section_lines = self.inp_lines[section_start:section_end]
        dtypes = getattr(self, section + '_dtypes')

        elements = []
        last_profile = ''
        for i, line in enumerate(section_lines):
            if re.match('^[\s]*\;', line) or re.match('^[\s]*$', line) or re.match('^[\s]*\[', line):
                continue
            else:
                line = line.split()
                if line[0].strip()[0] == '"':
                    item_indx = 1
                    name = ''
                    for i, item in enumerate(line):
                        name += item + ' '
                        if re.search('"$', item):
                            second_quote_index = i
                            break

                    new_line = [name.strip()] + line[(second_quote_index + 1):]
                    line = new_line
                else:
                    line[0] = '"' + line[0] + '"'

                if len(line) != 6:
                    if len(line) < 2 or len(line) > 6:
                        raise Exception("Error: swmmr.get_Profiles: Unexpected line format encountered: " + str(line))

                current_profile = line[0]
                if current_profile != last_profile:
                    last_profile = current_profile
                    current_ordinal = 1

                for link in line[1:]:
                    element = {'Name'       : ':'.join([current_profile, str(current_ordinal)]),
                               'Profile'    : current_profile,
                               'Link'       : link,
                               'Ordinal'    : current_ordinal}
                    current_ordinal += 1
                    elements.append(element)

        return elements

    def get_Controls(self):
        section = 'Controls'
        if section not in self.section_locations.keys():
            return []

        section_start = self.section_locations[section][0]
        section_end = self.section_locations[section][1]
        section_lines = self.inp_lines[section_start:section_end]

        elements = []
        current_rule = None
        last_description = ''
        current_description = ''
        current_ordinal = 1
        for i, line in enumerate(section_lines):
            if i == (len(section_lines) - 1) and current_rule is not None:
                name = ':'.join([str(current_ordinal), current_rule_name])
                elements.append({'Name' : name,
                                 'RuleName' : current_rule_name,
                                 'Ordinal' : current_ordinal,
                                 'RuleText' : current_rule,
                                 'Description' : re.sub('\n$', '', current_description, count = 1) if current_description is not None else None})
            elif re.match('^[\s]*$', line) or re.match('^[\s]*\[', line):
                continue
            else:
                line_split = line.split(None, 2)
                if line_split[0] == 'RULE':
                    if current_rule is not None:
                        name = ':'.join([str(current_ordinal), current_rule_name])
                        elements.append({'Name' : name,
                                         'RuleName' : current_rule_name,
                                         'Ordinal' : current_ordinal,
                                         'RuleText' : current_rule,
                                         'Description' : re.sub('\n$', '', current_description, count=1) if current_description is not None else None})
                    current_ordinal += 1
                    current_rule_name = line_split[1]
                    current_rule = ''
                    if last_description != '':
                        current_description = last_description
                        current_description = filter(lambda c: c not in ";", current_description)
                        last_description = ''
                    else:
                        current_description = None
                elif re.match('^[\s]*\;', line):
                    last_description += line
                else:
                    if last_description != '':
                        current_rule += last_description
                        last_description = ''

                    current_rule += line

        return elements

    def get_TransectPoints(self):
        section = 'TransectPoints'
        if section not in self.section_locations.keys():
            return []

        section_start = self.section_locations[section][0]
        section_end = self.section_locations[section][1]
        section_lines = self.inp_lines[section_start:section_end]

        elements = []

        description = None
        current_leftroughness = None
        past_header = False
        for i, line in enumerate(section_lines):
            if (re.match('^[\s]*\;\;', line) and not past_header) or re.match('^[\s]*$', line) or re.match('^[\s]*\[', line):
                continue
            if re.match('^[\s]*\;', line):
                past_header = True
                line = line.strip('\;')
                if description is None: description = line
                else: description = description + line
                continue
            else:
                past_header = True
                if re.search(';', line):
                    line, eol_desc = re.split('[ ;]*;', line, maxsplit=1)
                    if description:
                        description = description + eol_desc
                    else:
                        description = eol_desc
                line = line.split()

                line_marker = line[0]
                if line_marker == 'NC':
                    if len(line) != 4:
                        raise Exception('Error: swmmlib.get_TransectPoints: Unexpected line format encountered: ' + str(line))
                    current_description = description
                    description = None
                    leftroughness = float(line[1])
                    rightroughness = float(line[2])
                    channelroughness = float(line[3])
                    current_ordinal = 1
                elif line_marker == 'X1':
                    if len(line) != 10:
                        raise Exception('Error: swmmlib.get_TransectPoints: Unexpected line format encountered: ' + str(line))
                    transectname = line[1]
                    numstations = int(line[2])
                    left_bankstation = float(line[3])
                    right_bankstation = float(line[4])
                    meander_mod = float(line[7])
                    station_mod = float(line[8])
                    elev_mod = float(line[9])
                elif line_marker == 'GR':
                    if (len(line) % 2) != 1:
                        raise Exception('Error: swmmlib.get_TransectPoints: Unexpected line format encountered: ' + str(line))

                    line = line[1:]
                    for i in range(0, len(line), 2):
                        if current_description is not None:
                            current_description = current_description.strip('\n')

                        element = {'Name'               : ':'.join([transectname, str(current_ordinal)]),
                                   'TransectName'       : transectname,
                                   'Ordinal'            : current_ordinal,
                                   'StationCount'       : numstations,
                                   'LeftBankRoughness'  : leftroughness,
                                   'RightBankRoughness' : rightroughness,
                                   'ChannelRoughness'   : channelroughness,
                                   'LeftBankStation'    : left_bankstation,
                                   'RightBankStation'   : right_bankstation,
                                   'StationsModifier'   : station_mod,
                                   'ElevationsModifier' : elev_mod,
                                   'MeanderModifier'    : meander_mod,
                                   'Description'        : re.sub('\n$', '', current_description, count=1) if current_description is not None else None,
                                   'Elevation_ft'       : float(line[i]),
                                   'Station_ft'         : float(line[i+1])
                                   }
                        current_ordinal += 1
                        elements.append(element)

        return elements

    def get_Treatments(self):
        section = 'Treatments'
        if section not in self.section_locations.keys():
            return []

        section_start = self.section_locations[section][0]
        section_end = self.section_locations[section][1]
        section_lines = self.inp_lines[section_start:section_end]
        fields = getattr(self, section + '_fields')
        dtypes = getattr(self, section + '_dtypes')

        elements = []
        description = None
        past_header = False
        for i, line in enumerate(section_lines):
            if (re.match('^[\s]*\;\;', line) and not past_header) or re.match('^[\s]*$', line) or re.match('^[\s]*\[', line):
                continue
            if re.match('^[\s]*\;', line):
                past_header = True
                line = line.strip('\;')
                if description is None: description = line
                else: description = description + line
                continue
            else:
                past_header = True
                if re.search(';', line):
                    line, eol_desc = re.split('[ ;]*;', line, maxsplit=1)
                    if description:
                        description = description + eol_desc
                    else:
                        description = eol_desc
                line = line.split(None, 2)
                if len(line) < len(fields):
                    raise Exception("Error: swmmlib.get_Treatments: Unexpected line format encountered: " + str(line))
                for j, value in enumerate(line):
                    if value is not None:
                        value = value.strip()
                        line[j] = dtypes[j](value)
                params = dict(zip(fields, line))
                params['Name'] = ':'.join([params['Node'], params['Pollutant']])
                params['Description'] = re.sub('\n$', '', description, count=1) if description is not None else None
                description = None
                elements.append(params)

        return elements

    ## links
    def get_Conduits(self):
        section = 'Conduits'
        if section not in self.section_locations.keys():
            return []

        section_start = self.section_locations[section][0]
        section_end = self.section_locations[section][1]
        section_lines = self.inp_lines[section_start:section_end]
        fields = getattr(self, section + '_fields')
        dtypes = getattr(self, section + '_dtypes')

        elements = []
        description = None
        past_header = False
        for i, line in enumerate(section_lines):
            if (re.match('^[\s]*\;\;', line) and not past_header) or re.match('^[\s]*$', line) or re.match('^[\s]*\[', line):
                continue
            if re.match('^[\s]*\;', line):
                past_header = True
                line = line.strip('\;')
                if description is None: description = line
                else: description = description + line
                continue
            else:
                past_header = True
                if re.search(';', line):
                    line, eol_desc = re.split('[ ;]*;', line, maxsplit=1)
                    if description:
                        description = description + eol_desc
                    else:
                        description = eol_desc
                line = line.split()
                if len(line) != len(fields):
                    raise Exception("Error: swmmlib.get_Conduits: Unexpected line format encountered: " + str(line))
                for j, value in enumerate(line):
                    if value is not None:
                        line[j] = dtypes[j](value)
                params = dict(zip(fields, line))
                params['Description'] = re.sub('\n$', '', description, count=1) if description is not None else None
                elements.append(params)
                description = None

        if len(elements) > 0:
            for subclass in getattr(self, section + '_subclasses'):
                elements = getattr(self, 'assign_' + subclass)(section, elements)
                
        return elements

    def assign_Losses(self, section, elements):
        losses_elements = []
        losses_fields = getattr(self, 'Losses_fields')
        losses_dtypes = getattr(self, 'Losses_dtypes')
        losses_defaults = [0, 0, 0, 'NO']

        if 'Losses' in self.section_locations.keys():
            losses_start = self.section_locations['Losses'][0]
            losses_end = self.section_locations['Losses'][1]

            losses_lines = self.inp_lines[losses_start:losses_end]

            description = None
            description_name = 'LossesDescription'
            past_header = False
            for i, line in enumerate(losses_lines):
                if (re.match('^[\s]*\;\;', line) and not past_header) or re.match('^[\s]*$', line) or re.match('^[\s]*\[', line):
                    continue
                if re.match('^[\s]*\;', line):
                    past_header = True
                    line = line.strip('\;')
                    if description is None: description = line
                    else: description = description + line
                    continue
                else:
                    past_header = True
                    if re.search(';', line):
                        line, eol_desc = re.split('[ ;]*;', line, maxsplit=1)
                        if description:
                            description = description + eol_desc
                        else:
                            description = eol_desc
                    line = line.split()
                    if len(line) != len(losses_fields):
                        raise Exception("Error: swmmlib.assign_Losses: Unexpected line format encountered: " + str(line))
                    for j, value in enumerate(line):
                        if value is not None:
                            line[j] = losses_dtypes[j](value)
                    params = dict(zip(losses_fields, line))
                    params[description_name] = re.sub('\n$', '', description, count=1) if description is not None else None
                    description = None
                    losses_elements.append(params)

        fields = getattr(self, "Conduits_fields")
        if len(losses_elements) > 0:
            for i in xrange(len(elements)):
                name = elements[i][fields[0]]
                losses_have_element = False
                for j in xrange(len(losses_elements)):
                    losses_name = losses_elements[j][losses_fields[0]]
                    if name == losses_name:
                        for fieldname in losses_fields[1:]:
                            elements[i][fieldname] = losses_elements[j][fieldname]
                        elements[i][description_name] = losses_elements[j][description_name]
                        losses_have_element = True
                        break
                if not losses_have_element:
                    for j, fieldname in enumerate(losses_fields[1:]):
                        elements[i][fieldname] = losses_defaults[j]
        else:
            for i in xrange(len(elements)):
                for j, field_name in enumerate(losses_fields[1:]):
                    elements[i][field_name] = losses_defaults[j]

        return elements

    def assign_XSections(self, section, elements):
        if 'XSections' not in self.section_locations.keys():
            raise Exception("Error: swmmlib.assign_XSections: Conduits loaded without xsections")
        else:
            section_start = self.section_locations['XSections'][0]
            section_end = self.section_locations['XSections'][1]

            xsections_elements = []
            xsections_fields = getattr(self, 'XSections_fields')
            xsections_dtypes = getattr(self, 'XSections_dtypes')

            xsections_lines = self.inp_lines[section_start:section_end]

            description = None
            description_name = 'XSectionsDescription'
            past_header = False
            for i, line in enumerate(xsections_lines):
                if (re.match('^[\s]*\;\;', line) and not past_header) or re.match('^[\s]*$', line) or re.match('^[\s]*\[', line):
                    continue
                if re.match('^[\s]*\;', line):
                    past_header = True
                    line = line.strip('\;')
                    if description is None: description = line
                    else: description = description + line
                    continue
                else:
                    past_header = True
                    if re.search(';', line):
                        line, eol_desc = re.split('[ ;]*;', line, maxsplit=1)
                        if description:
                            description = description + eol_desc
                        else:
                            description = eol_desc
                    line = line.split()
                    if len(line) != len(xsections_fields):
                        if len(line) == (len(xsections_fields) - 1):
                            line.append(None)
                        elif len(line) == (len(xsections_fields) - 2):
                            line.extend([None, None])
                        else:
                            raise Exception("Error: swmmlib.assign_XSections: Unexpected line format encountered: " + str(line))

                    for j, value in enumerate(line):
                        if value is not None:
                            line[j] = xsections_dtypes[j](value)
                    params = dict(zip(xsections_fields, line))
                    params[description_name] = re.sub('\n$', '', description, count=1) if description is not None else None
                    description = None
                    xsections_elements.append(params)
            
            if len(xsections_elements) == 0:
                raise Exception("Error: swmmlib.assign_XSections: " + section + " loaded without XSections")
            else:
                fields = getattr(self, section + "_fields")
                for i in xrange(len(elements)):
                    name = elements[i][fields[0]]
                    xsections_have_element = False
                    for j in xrange(len(xsections_elements)):
                        xsections_name = xsections_elements[j][xsections_fields[0]]
                        if name == xsections_name:
                            for fieldname in xsections_fields[1:]:
                                elements[i][fieldname] = xsections_elements[j][fieldname]
                            elements[i][description_name] = xsections_elements[j][description_name]
                            xsections_have_element = True
                            break
                    if not xsections_have_element:
                        raise Exception("Error: swmmlib.assign_XSections: No xsection record for link " + name)
                return elements

    def elements2XML(self, section, elements):
        if len(elements) > 0:
            xml_str = '\t<' + section + '>\n'
            for element in elements:
                xml_str += '\t\t<Element>\n'
                for parameter, value in element.items():
                    if value is None:
                        value = 'NULL'
                    elif isinstance(value, str): 
                        value = value.replace('&', '&amp;')
                        value = value.replace('"', '&quot;')
                        value = value.replace('<', '&lt;')
                        value = value.replace('>', '&gt;')
                        value = value.replace("'", '&apos;')
                        value = value.replace("\n", "\\n")
                        value = value.replace("\x92", "'") # replace foot mark with apostrophe
                        non_ascii = [ch for ch in value if ord(ch) >= 128]
                        if len(non_ascii) != 0:
                            raise Exception('Error: swmmlib.elements2XML: Non-ascii values ' + str(non_ascii) \
                                    + ' in ' + section + ' for parameter ' + parameter + '.')
                        try:
                            if len(value) > 5000:
                                raise Exception("Parameter value is too long.")
                        except:
                            traceback.print_exc()
                            code.interact(local=locals())
                    xml_str += '\t\t\t<' + parameter + '>' + str(value) + '</' + parameter + '>\n'
                xml_str += '\t\t</Element>\n'
            xml_str += '\t</' + section + '>\n'

            return xml_str
        else:
            return ''
            
    def get(self, section, xml=False):
        elements = getattr(self, 'get_' + section)()

        if xml:
            return self.elements2XML(section, elements)
        else:
            return elements

    ## Pumps
    def get_Pumps(self):
        section = 'Pumps'
        if section not in self.section_locations.keys():
            return []

        section_start = self.section_locations[section][0]
        section_end = self.section_locations[section][1]
        section_lines = self.inp_lines[section_start:section_end]
        fields = getattr(self, section + '_fields')
        dtypes = getattr(self, section + '_dtypes')

        elements = []
        description = None
        past_header = False
        for i, line in enumerate(section_lines):
            if (re.match('^[\s]*\;\;', line) and not past_header) or re.match('^[\s]*$', line) or re.match('^[\s]*\[', line):
                continue
            if re.match('^[\s]*\;', line):
                past_header = True
                line = line.strip('\;')
                if description is None: description = line
                else: description = description + line
            else:
                past_header = True
                if re.search(';', line):
                    line, eol_desc = re.split('[ ;]*;', line, maxsplit=1)
                    if description:
                        description = description + eol_desc
                    else:
                        description = eol_desc
                line = line.split()
                if len(line) != len(fields):
                    raise Exception("Error: swmmlib.get_Pumps: Unexpected line format encountered: " + str(line))
                for j, value in enumerate(line):
                    if value is not None:
                        line[j] = dtypes[j](value)
                params = dict(zip(fields, line))
                params['Description'] = re.sub('\n$', '', description, count=1) if description is not None else None
                elements.append(params)
                description = None

        if len(elements) > 0:
            for subclass in getattr(self, section + '_subclasses'):
                elements = getattr(self, 'assign_' + subclass)(section, elements)

        return elements

    def get_Orifices(self):
        section = 'Orifices'
        if section not in self.section_locations.keys():
            return []

        section_start = self.section_locations[section][0]
        section_end = self.section_locations[section][1]
        section_lines = self.inp_lines[section_start:section_end]
        fields = getattr(self, section + '_fields')
        dtypes = getattr(self, section + '_dtypes')

        elements = []
        description = None
        past_header = False
        for i, line in enumerate(section_lines):
            if (re.match('^[\s]*\;\;', line) and not past_header) or re.match('^[\s]*$', line) or re.match('^[\s]*\[', line):
                continue
            if re.match('^[\s]*\;', line):
                past_header = True
                line = line.strip('\;')
                if description is None: description = line
                else: description = description + line
                continue
            else:
                past_header = True
                if re.search(';', line):
                    line, eol_desc = re.split('[ ;]*;', line, maxsplit=1)
                    if description:
                        description = description + eol_desc
                    else:
                        description = eol_desc
                line = line.split()

                if len(line) != len(fields):
                    raise Exception("Error: swmmlib.get_Orifices: Unexpected line format encountered: " + str(line))
                for j, value in enumerate(line):
                    if value is not None:
                        line[j] = dtypes[j](value)
                params = dict(zip(fields, line))
                params['Description'] = re.sub('\n$', '', description, count=1) if description is not None else None
                elements.append(params)
                description = None

        if len(elements) > 0:
            for subclass in getattr(self, section + '_subclasses'):
                elements = getattr(self, 'assign_' + subclass)(section, elements)

        return elements

    def get_Weirs(self):
        section = 'Weirs'
        if section not in self.section_locations.keys():
            return []

        section_start = self.section_locations[section][0]
        section_end = self.section_locations[section][1]
        section_lines = self.inp_lines[section_start:section_end]
        fields = getattr(self, section + '_fields')
        dtypes = getattr(self, section + '_dtypes')

        elements = []
        description = None
        past_header = False
        for i, line in enumerate(section_lines):
            if (re.match('^[\s]*\;\;', line) and not past_header) or re.match('^[\s]*$', line) or re.match('^[\s]*\[', line):
                continue
            if re.match('^[\s]*\;', line):
                past_header = True
                line = line.strip('\;')
                if description is None: description = line
                else: description = description + line
                continue
            else:
                past_header = True
                if re.search(';', line):
                    line, eol_desc = re.split('[ ;]*;', line, maxsplit=1)
                    if description:
                        description = description + eol_desc
                    else:
                        description = eol_desc

                line = line.split()
                if len(line) != len(fields):
                    if len(line) == (len(fields) - 1):
                        line.append(None)
                    else:
                        raise Exception("Error: swmmlib.get_Weirs: Unexpected line format encountered: " + str(line))
                for j, value in enumerate(line):
                    if value is not None:
                        line[j] = dtypes[j](value)
                params = dict(zip(fields, line))
                params['Description'] = re.sub('\n$', '', description, count=1) if description is not None else None
                elements.append(params)
                description = None

        if len(elements) > 0:
            for subclass in getattr(self, section + '_subclasses'):
                elements = getattr(self, 'assign_' + subclass)(section, elements)

        return elements

    def get_Outlets(self):
        section = 'Outlets'
        if section not in self.section_locations.keys():
            return []

        section_start = self.section_locations[section][0]
        section_end = self.section_locations[section][1]
        section_lines = self.inp_lines[section_start:section_end]
        fields = getattr(self, section + '_fields')
        dtypes = getattr(self, section + '_dtypes')

        elements = []
        description = None
        past_header = False
        for i, line in enumerate(section_lines):
            if (re.match('^[\s]*\;\;', line) and not past_header) or re.match('^[\s]*$', line) or re.match('^[\s]*\[', line):
                continue
            if re.match('^[\s]*\;', line):
                past_header = True
                line = line.strip('\;')
                if description is None: description = line
                else: description = description + line
                continue
            else:
                past_header = True
                if re.search(';', line):
                    line, eol_desc = re.split('[ ;]*;', line, maxsplit=1)
                    if description:
                        description = description + eol_desc
                    else:
                        description = eol_desc

                line = line.split()
                if re.match('^FUNCTIONAL', line[fields.index('OutletType')]):
                    line.insert(fields.index('CurveName'), None)
                elif re.match('^TABULAR', line[fields.index('OutletType')]):
                    line.insert(fields.index('FunctionalCoeff'), None)
                    line.insert(fields.index('FunctionalExponent'), None)
                else:
                    raise Exception("Error: swmmlib.get_Outlets: Unexpected Outlet type encountered: " + str(line))
                    
                if len(line) != len(fields):
                    raise Exception("Error: swmmlib.get_Outlets: Unexpected line format encountered: " + str(line))
                for j, value in enumerate(line):
                    if value is not None:
                        line[j] = dtypes[j](value)
                params = dict(zip(fields, line))
                params['Description'] = re.sub('\n$', '', description, count=1) if description is not None else None
                elements.append(params)
                description = None

        if len(elements) > 0:
            for subclass in getattr(self, section + '_subclasses'):
                elements = getattr(self, 'assign_' + subclass)(section, elements)

        return elements

    def assign_Tags(self, section, elements):
        tags_elements = []
        if 'Tags' in self.section_locations.keys():
            tags_start = self.section_locations['Tags'][0]
            tags_end = self.section_locations['Tags'][1]

            tags_lines = self.inp_lines[tags_start:tags_end]
            tags_fields = getattr(self, 'Tags_fields')
            tags_dtypes = getattr(self, 'Tags_dtypes')

            for i, line in enumerate(tags_lines):
                if re.match('^[\s]*\;', line) or re.match('^[\s]*$', line) or re.match('^[\s]*\[', line):
                    continue
                else:
                    line = line.split()
                    if len(line) != len(tags_fields): 
                        raise Exception("Error: swmmlib.assign_Tags: Unexpected line format encountered: " + str(line))
                    for j, value in enumerate(line):
                        if value is not None:
                            line[j] = tags_dtypes[j](value)
                    params = dict(zip(tags_fields, line))
                    tags_elements.append(params)

        tag_types = {'Junctions'        : 'Node',
                     'Outfalls'         : 'Node',
                     'Dividers'         : 'Node',
                     'Storage'          : 'Node',
                     'RainGages'        : 'Gage',
                     'Subcatchments'    : 'Subcatch',
                     'Conduits'         : 'Link',
                     'Pumps'            : 'Link',
                     'Weirs'            : 'Link',
                     'Orifices'         : 'Link',
                     'Outlets'          : 'Link'}

        tag_type = tag_types[section]

        if len(tags_elements) > 0:
            fields = getattr(self, section + '_fields')
            for i in xrange(len(elements)):
                name = elements[i][fields[0]]
                tags_have_element = False
                for j in xrange(len(tags_elements)):
                    this_tag_type = tags_elements[j]['Type']
                    this_tag_name = tags_elements[j]['Name']
                    if name == this_tag_name and this_tag_type == tag_type:
                        elements[i]['Tag'] = tags_elements[j]['Tag']
                        tags_have_element = True
                        break
                if not tags_have_element:
                    elements[i]['Tag'] = None
        else:
            for i in xrange(len(elements)):
                    elements[i]['Tag'] = None

        return elements

    def get_Pollutants(self):
        section = 'Pollutants'
        if section not in self.section_locations.keys():
            return []

        section_start = self.section_locations[section][0]
        section_end = self.section_locations[section][1]
        section_lines = self.inp_lines[section_start:section_end]
        fields = getattr(self, section + '_fields')
        dtypes = getattr(self, section + '_dtypes')

        elements = []
        description = None
        past_header = False
        for i, line in enumerate(section_lines):
            if (re.match('^[\s]*\;\;', line) and not past_header) or re.match('^[\s]*$', line) or re.match('^[\s]*\[', line):
                continue
            if re.match('^[\s]*\;', line):
                past_header = True
                line = line.strip('\;')
                if description is None: description = line
                else: description = description + line
                continue
            else:
                past_header = True
                if re.search(';', line):
                    line, eol_desc = re.split('[ ;]*;', line, maxsplit=1)
                    if description:
                        description = description + eol_desc
                    else:
                        description = eol_desc

                line = line.split()
                if len(line) != len(fields):
                    raise Exception("Error: swmmlib.get_Pollutants: Unexpected line format encountered: " + str(line))
                for j, value in enumerate(line):
                    if value is not None:
                        line[j] = dtypes[j](value)
                params = dict(zip(fields, line))
                params['Description'] = re.sub('\n$', '', description, count=1) if description is not None else None
                description = None
                elements.append(params)

        return elements

    def get_LandUses(self):
        section = 'LandUses'
        if section not in self.section_locations.keys():
            return []

        section_start = self.section_locations[section][0]
        section_end = self.section_locations[section][1]
        section_lines = self.inp_lines[section_start:section_end]
        fields = getattr(self, section + '_fields')
        dtypes = getattr(self, section + '_dtypes')

        elements = []
        description = None
        past_header = False
        for i, line in enumerate(section_lines):
            if (re.match('^[\s]*\;\;', line) and not past_header) or re.match('^[\s]*$', line) or re.match('^[\s]*\[', line):
                continue
            if re.match('^[\s]*\;', line):
                past_header = True
                line = line.strip('\;')
                if description is None: description = line
                else: description = description + line
                continue
            else:
                past_header = True
                if re.search(';', line):
                    line, eol_desc = re.split('[ ;]*;', line, maxsplit=1)
                    if description:
                        description = description + eol_desc
                    else:
                        description = eol_desc
                line = line.split()
                if len(line) != len(fields):
                    raise Exception("Error: swmmlib.get_LandUses: Unexpected line format encountered: " + str(line))
                for j, value in enumerate(line):
                    if value is not None:
                        try:
                            line[j] = dtypes[j](value)
                        except:
                            traceback.print_exc()
                params = dict(zip(fields, line))
                params['Description'] = re.sub('\n$', '', description, count=1) if description is not None else None
                elements.append(params)
                description = None

        return elements

    def get_Coverages(self):
        section = 'Coverages'
        if section not in self.section_locations.keys():
            return []

        section_start = self.section_locations[section][0]
        section_end = self.section_locations[section][1]
        section_lines = self.inp_lines[section_start:section_end]
        fields = getattr(self, section + '_fields')
        dtypes = getattr(self, section + '_dtypes')

        elements = []
        description = None
        past_header = False
        for i, line in enumerate(section_lines):
            if (re.match('^[\s]*\;\;', line) and not past_header) or re.match('^[\s]*$', line) or re.match('^[\s]*\[', line):
                continue
            if re.match('^[\s]*\;', line):
                past_header = True
                line = line.strip('\;')
                if description is None: description = line
                else: description = description + line
                continue
            else:
                past_header = True
                if re.search(';', line):
                    line, eol_desc = re.split('[ ;]*;', line, maxsplit=1)
                    if description:
                        description = description + eol_desc
                    else:
                        description = eol_desc

                line = line.split()
                if len(line) != len(fields):
                    raise Exception("Error: swmmlib.get_Coverages: Unexpected line format encountered: " + str(line))
                for j, value in enumerate(line):
                    if value is not None:
                        line[j] = dtypes[j](value)
                params = dict(zip(fields, line))
                name = ':'.join([params['Subcatchment'], params['LandUse']])
                params['Name'] = name
                params['Description'] = re.sub('\n$', '', description, count=1) if description is not None else None
                description = None
                elements.append(params)

        return elements

    def get_Loadings(self):
        section = 'Loadings'
        if section not in self.section_locations.keys():
            return []

        section_start = self.section_locations[section][0]
        section_end = self.section_locations[section][1]
        section_lines = self.inp_lines[section_start:section_end]
        fields = getattr(self, section + '_fields')
        dtypes = getattr(self, section + '_dtypes')

        elements = []
        description = None
        past_header = False
        for i, line in enumerate(section_lines):
            if (re.match('^[\s]*\;\;', line) and not past_header) or re.match('^[\s]*$', line) or re.match('^[\s]*\[', line):
                continue
            if re.match('^[\s]*\;', line):
                past_header = True 
                line = line.strip('\;')
                if description is None: description = line
                else: description = description + line
                continue
            else:
                past_header = True
                if re.search(';', line):
                    line, eol_desc = re.split('[ ;]*;', line, maxsplit=1)
                    if description:
                        description = description + eol_desc
                    else:
                        description = eol_desc
                line = line.split()
                if len(line) != len(fields):
                    raise Exception("Error: swmmlib.get_Loadings: Unexpected line format encountered: " + str(line))
                for j, value in enumerate(line):
                    if value is not None:
                        line[j] = dtypes[j](value)
                params = dict(zip(fields, line))
                name = ':'.join([params['Subcatchment'], params['Pollutant']])
                params['Name'] = name
                params['Description'] = re.sub('\n$', '', description, count=1) if description is not None else None
                description = None
                elements.append(params)

        return elements

    def get_BuildUp(self):
        section = 'BuildUp'
        if section not in self.section_locations.keys():
            return []

        section_start = self.section_locations[section][0]
        section_end = self.section_locations[section][1]
        section_lines = self.inp_lines[section_start:section_end]
        fields = getattr(self, section + '_fields')
        dtypes = getattr(self, section + '_dtypes')

        elements = []
        description = None
        past_header = False
        for i, line in enumerate(section_lines):
            if (re.match('^[\s]*\;\;', line) and not past_header) or re.match('^[\s]*$', line) or re.match('^[\s]*\[', line):
                continue
            if re.match('^[\s]*\;', line):
                past_header = True
                line = line.strip('\;')
                if description is None: description = line
                else: description = description + line
                continue
            else:
                past_header = True
                if re.search(';', line):
                    line, eol_desc = re.split('[ ;]*;', line, maxsplit=1)
                    if description:
                        description = description + eol_desc
                    else:
                        description = eol_desc
                line = line.split()
                timeseries_marker = line[fields.index('Coeff3')]
                try:
                    dummy = float(timeseries_marker)
                except:
                    line.insert(fields.index('Coeff3'), None)
                else:
                    line.insert(fields.index('TimeSeries'), None)

                if len(line) != len(fields):
                    raise Exception("Error: swmmlib.get_BuildUp: Unexpected line format encountered: " + str(line))
                for j, value in enumerate(line):
                    if value is not None:
                        line[j] = dtypes[j](value)
                params = dict(zip(fields, line))
                name = ':'.join([params['LandUse'], params['Pollutant']])
                params['Name'] = name
                params['Description'] = re.sub('\n$', '', description, count=1) if description is not None else None
                description = None
                elements.append(params)

        return elements

    def get_WashOff(self):
        section = 'WashOff'
        if section not in self.section_locations.keys():
            return []

        section_start = self.section_locations[section][0]
        section_end = self.section_locations[section][1]
        section_lines = self.inp_lines[section_start:section_end]
        fields = getattr(self, section + '_fields')
        dtypes = getattr(self, section + '_dtypes')

        elements = []
        description = None
        past_header = False
        for i, line in enumerate(section_lines):
            if (re.match('^[\s]*\;\;', line) and not past_header) or re.match('^[\s]*$', line) or re.match('^[\s]*\[', line):
                continue
            if re.match('^[\s]*\;', line):
                past_header = True
                line = line.strip('\;')
                if description is None: description = line
                else: description = description + line
                continue
            else:
                past_header = True
                if re.search(';', line):
                    line, eol_desc = re.split('[ ;]*;', line, maxsplit=1)
                    if description:
                        description = description + eol_desc
                    else:
                        description = eol_desc

                line = line.split()
                if len(line) != len(fields):
                    raise Exception("Error: swmmlib.get_WashOff: Unexpected line format encountered: " + str(line))
                for j, value in enumerate(line):
                    if value is not None:
                        line[j] = dtypes[j](value)
                params = dict(zip(fields, line))
                name = ':'.join([params['LandUse'], params['Pollutant']])
                params['Name'] = name
                params['Description'] = re.sub('\n$', '', description, count=1) if description is not None else None
                description = None
                elements.append(params)

        return elements

    def get_CurvePoints(self):
        section = 'CurvePoints'
        if section not in self.section_locations.keys():
            return []

        section_start = self.section_locations[section][0]
        section_end = self.section_locations[section][1]
        section_lines = self.inp_lines[section_start:section_end]
        fields = getattr(self, section + '_fields')
        dtypes = getattr(self, section + '_dtypes')

        elements = []
        new_curve = True
        description = None
        past_header = False
        for i, line in enumerate(section_lines):
            if (re.match('^[\s]*\;\;', line) and not past_header) or re.match('^[\s]*$', line) or re.match('^[\s]*\[', line):
                continue
            elif re.match('^[\s]*\;', line):
                past_header = True
                line = line.strip('\;')
                if description is None: description = line
                else: description = description + line
                continue
            else:
                past_header = True
                if re.search(';', line):
                    line, eol_desc = re.split('[ ;]*;', line, maxsplit=1)
                    if description:
                        description = description + eol_desc
                    else:
                        description = eol_desc
                line = line.split()
                try:
                    dummy = float(line[1])
                except:
                    new_curve = True
                    if len(line) != 4:
                        raise Exception("Error: swmmr.get_CurvePoints: unexpected line format encountered: " + str(line))
                else:
                    new_curve = False
                    if len(line) != 3:
                        raise Exception("Error: swmmr.get_CurvePoints: unexpected line format encountered: " + str(line))

                if new_curve:
                    current_ordinal = 1
                    current_type = line[1]
                else:
                    line.insert(fields.index('Type'), current_type)

                for j, value in enumerate(line):
                    line[j] = dtypes[j](value)

                params = dict(zip(fields, line))
                name = ':'.join([params['Curve'], str(current_ordinal)])
                params['Name'] = name
                params['Ordinal'] = current_ordinal
                params['Description'] = re.sub('\n$', '', description, count=1) if description else None
                description = None
                elements.append(params)
                current_ordinal += 1

        return elements

    def get_TimeSeriesPoints(self):
        section = 'TimeSeriesPoints'
        if section not in self.section_locations.keys():
            return []

        section_start = self.section_locations[section][0]
        section_end = self.section_locations[section][1]
        section_lines = self.inp_lines[section_start:section_end]
        fields = getattr(self, section + '_fields')
        dtypes = getattr(self, section + '_dtypes')

        elements = []
        description = None
        current_series = None
        past_header = False
        for i, line in enumerate(section_lines):
            if (re.match('^[\s]*\;\;', line) and not past_header) or re.match('^[\s]*$', line) or re.match('^[\s]*\[', line):
                continue
            elif re.match('^[\s]*\;', line):
                past_header = True
                line = line.strip('\;')
                if description is None: description = line
                else: description = description + line
                continue
            else:
                past_header = True
                if re.search(';', line):
                    line, eol_desc = re.split('[ ;]*;', line, maxsplit=1)
                    if description:
                        description = description + eol_desc
                    else:
                        description = eol_desc
                line = line.split()
                series = line[0]
                if series != current_series:
                    new_series = True
                    current_series = series
                    current_ordinal = 1

                if line[1] == 'FILE' and len(line) > 3:
                    line = [line[0], line[1], ' '.join(line[2:])]

                if len(line) == 3:
                    if 'FILE' in line:
                        line.remove('FILE')
                        line.extend([None, None, None])
                    else:
                        line.insert(fields.index('FileName'), None)
                        line.insert(fields.index('DateTime'), None)
                else:
                    dtime = ' '.join(line[1:3])
                    #dtime = datetime.strptime(dtime_str, '%m/%d/%Y %H:%M')
                    line[1] = dtime
                    line = line[:2] + line[3:]
                    line.insert(fields.index('FileName'), None)
                    line.insert(fields.index('Duration'), None)

                if len(line) != len(fields):
                    raise Exception('Error: swmmlib.get_TimeSeriesPoints: Unexpected line format encountered: ' + str(line))

                for j, value in enumerate(line):
                    if value is not None:
                        line[j] = dtypes[j](value)

                params = dict(zip(fields, line))
                name = ':'.join([params['TimeSeries'], str(current_ordinal)])
                params['Name'] = name
                params['Ordinal'] = current_ordinal
                params['Description'] = re.sub('\n$', '', description, count=1) if description else None
                if params['FileName'] is not None and self.require_support_files:
                    fpath = os.path.join(os.path.dirname(self.inp_path), params['FileName'].strip(' \t\n"'))
                    if not os.path.exists(fpath):
                        raise Exception("Can't find support file '" + fpath + "' referenced in [TIMESERIES]")
                    else:
                        params['FileName'] = '"' + os.path.basename(fpath) + '"'
                        with open(fpath, 'rb') as f:
                            fcontents = f.read()
                        fbuffer = buffer(fcontents)
                        md5 = hashlib.md5(fcontents).hexdigest()
                        params['FileMD5'] = md5
                        self.files[md5] = fbuffer
                else:
                    params['FileMD5'] = None

                description = None
                elements.append(params)
                current_ordinal += 1

        return elements

