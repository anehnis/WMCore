#!/usr/bin/env python
"""
_Report_

Job Report object

"""
__version__ = "$Revision: 1.7 $"
__revision__ = "$Id: Report.py,v 1.7 2010/02/10 17:08:55 mnorman Exp $"
__author__ = "evansde"

import pickle
import logging

from WMCore.Configuration import ConfigSection


from WMCore.DataStructs.File import File
from WMCore.DataStructs.Run  import Run



def jsonise(cfgSect):
    result = {}
    result['section_name_'] = cfgSect._internal_name
    result['sections_'] = []
    d = cfgSect.dictionary_()
    for key, value in d.items():
        if key in cfgSect._internal_children:
            result[key] = jsonise(value)
            result['sections_'].append(key)
        else:
            result[key] = value
    return result

def dejsonise(jsondict):
    section = ConfigSection(jsondict['section_name_'])
    sectionList = jsondict['sections_']
    for key, value in jsondict.items():
        if key in ("sections_", "section_name_"): continue
        if key in sectionList:
            setattr(section, key, dejsonise(value))
        else:
            setattr(section, key, value)
    return section



def checkFileForCompletion(file):
    """
    _checkFileForCompletion_

    Takes a DataStucts/File object (or derivative) and checks to see that the file is ready for transfer
    """

    #These should not be defaults
    if file['lfn'] == "" or file['size'] == 0 or file['events'] == 0:
        return False


    return True


class Report:

    def __init__(self, reportname = None):
        self.data = ConfigSection("FrameworkJobReport")


        #These are the objects that are put in place for management
        self.data.steps         = []



        if reportname:
            self.createSection(reportname = reportname)




    def parse(self, xmlfile):
        """
        _parse_

        Read in the FrameworkJobReport XML file produced
        by cmsRun and pull the information from it into this object

        """
        from WMCore.FwkJobReport.XMLParser import xmlToJobReport
        try:
            xmlToJobReport(self, xmlfile)
        except Exception, ex:
            msg = "Error reading XML job report file, possibly corrupt XML File:\n"
            msg += "Details: %s" % str(ex)
            self.addError(50115, "MissingJobReport", msg)

    def json(self):
        """
        _json_

        convert into JSON dictionary object

        """
        return jsonise(self.data)

    def dejson(self, jsondicts):
        """
        _dejson_

        Convert JSON provided into ConfigSection structure

        """
        self.data = dejsonise(self.data)

    def persist(self, filename):
        """
        _persist_


        """
        handle = open(filename, 'w')
        pickle.dump(self.data, handle)
        handle.close()
        return

    def unpersist(self, filename):
        """
        _unpersist_

        load object from file

        """

        handle = open(filename, 'r')
        self.data = pickle.load(handle)
        handle.close()
        return




    def addOutputModule(self, moduleName):
        """
        _addOutputModule_

        Add an entry for an output module.

        """

        self.report.outputModules.append(moduleName)
        
        self.report.output.section_(moduleName)

        outMod = getattr(self.report.output, moduleName)
        outMod.section_("files")
        outMod.section_("dataset")
        outMod.files.fileCount = 0

        return outMod


    def addOutputFile(self, outputModule, file):
        """
        _addFile_

        Add an output file to the outputModule provided

        """

        if not checkFileForCompletion(file):
            # Then the file is not complete, and should not be added
            return None

        # Now load the output module and create the file object
        outMod = getattr(self.report.output, outputModule, None)
        if outMod == None:
            outMod = self.addOutputModule(outputModule)
        count = outMod.files.fileCount
        fileSection = "file%s" % count
        outMod.files.section_(fileSection)
        fileRef = getattr(outMod.files, fileSection)
        outMod.files.fileCount += 1

        #First add the mandatory sections
        fileRef.section_("inputs")
        fileRef.section_("branches")
        fileRef.inputs.fileCount = 0

        # Now we need to eliminate the optional and non-primitives:
        # runs, parents, branches, locations and datasets
        keyList = file.keys()
        
        runDict = {}
        fileRef.section_("runs")
        for run in file['runs']:
            setattr(fileRef.runs, str(run.run), run.lumis)
        keyList.remove('runs')
        
        setattr(fileRef, 'parents', list(file['parents']))
        keyList.remove('parents')

        locationList = list(file['locations'])
        keyList.remove('locations')
        if 'newlocations' in file.keys():
            locationList.extend(list(file['newlocations']))
            keyList.remove('newlocations')
        setattr(fileRef, 'locations', locationList)


        # Now add the dataset
        # Assume one dataset per output module
        if outMod.dataset.listSections_() == []:
            # Then we haven't entered a dataset yet
            for entry in file['dataset']:
                setattr(outMod.dataset, entry, file['dataset'].get(entry, None))
            setattr(outMod.dataset, 'OutputModuleName', outputModule)


        # All right, the rest should be JSONalizable python primitives
        for entry in keyList:
            setattr(fileRef, entry, file[entry])

        #And we're done
        return fileRef


        


    def addInputSource(self, sourceName):
        """
        _addInputSource_

        Add an input source

        """
        self.report.input.section_(sourceName)
        srcMod = getattr(self.report.input, sourceName)
        srcMod.section_("files")
        srcMod.section_("dataset")
        srcMod.files.fileCount = 0

        return srcMod

    def addInputFile(self, sourceName, **attrs):
        """
        _addInputFile_

        Add an input file to the source named

        """
        srcMod = getattr(self.report.input, sourceName, None)
        if srcMod == None:
            srcMod = self.addInputSource(sourceName)
        count = srcMod.files.fileCount
        fileSection = "file%s" % count
        srcMod.files.section_(fileSection)
        fileRef = getattr(srcMod.files, fileSection)
        [ setattr(fileRef, k, v) for k, v in attrs.items()]
        srcMod.files.fileCount += 1

        fileRef.section_("runs")
        fileRef.section_("branches")

        return fileRef




    def addAnalysisFile(self, filename, **attrs):
        """
        _addAnalysisFile_

        Add and Analysis File

        """
        analysisFiles = self.report.analysis
        count = self.report.analysis.fileCount
        label = "file%s" % count

        analysisFiles.section_(label)
        newFile = getattr(analysisFiles, label)
        newFile.fileName = filename

        [ setattr(newFile, x, y) for x,y in attrs.items() ]

        self.report.analysis.fileCount += 1
        return


    def addError(self, exitCode, errorType, errorDetails):
        """
        _addError_

        Add an error report with an exitCode, type/class of error and
        details of the error as a string

        """
        self.report.errors.section_(errorType)
        errSection = getattr(self.report.errors, errorType)
        errorCount = getattr(errSection, "errorCount", 0)

        errEntry = "error%s" % errorCount
        errSection.section_(errEntry)
        errDetails = getattr(errSection, errEntry)
        errDetails.exitStatus = exitCode
        errDetails.description = errorDetails

        self.report.status = int(exitCode)
        setattr(errSection, "errorCount", errorCount +1)
        return


    def addSkippedFile(self, lfn, pfn):
        """
        _addSkippedFile_

        report a skipped input file

        """

        count = self.report.skipped.files.fileCount
        entry = "file%s" % count
        self.report.skipped.files.section_(entry)
        skipSect = getattr(self.report.skipped.files, entry)
        skipSect.PhysicalFileName = pfn
        skipSect.LogicalFileName = lfn
        self.report.skipped.files.fileCount += 1
        return



    def addSkippedEvent(self, run, event):
        """
        _addSkippedEvent_


        """
        self.report.skipped.events.section_(str(run))
        runsect = getattr(self.report.skipped.events, str(run))
        if not hasattr(runsect, "eventList"):
            runsect.eventList = []
        runsect.eventList.append(event)
        return


    def createSection(self, reportname):
        """
        _createSection_
        
        This creates a report section into self.report
        """

        if hasattr(self.data, reportname):
            msg = "Attempted to create pre-existing report section %s" %(reportname)
            logging.error(msg)
            return

        self.data.steps.append(reportname)

        
        self.reportname = reportname
        self.data.section_(reportname)
        self.report = getattr(self.data, reportname)
        self.report.id = None
        self.report.task = None
        self.report.workload = None
        self.report.status = 0
        self.report.outputModules = []
        
        # structure
        self.report.section_("site")
        self.report.section_("output")
        self.report.section_("input")
        self.report.section_("performance")
        self.report.section_("analysis")
        self.report.section_("errors")
        self.report.section_("skipped")
        self.report.section_("parameters")
        self.report.section_("logs")
        self.report.section_("cleanup")
        self.report.cleanup.section_("removed")
        self.report.cleanup.section_("unremoved")
        self.report.skipped.section_("events")
        self.report.skipped.section_("files")
        self.report.skipped.files.fileCount = 0
        self.report.analysis.fileCount = 0

        return


    def retrieveStep(self, step):
        """
        _retrieveStep_
        
        Grabs a report in the raw and returns it.  
        """

        reportSection = getattr(self.data, step, None)

        return reportSection

    


    def load(self, filename):
        """
        _load_
        
        This just maps to unpersist
        """

        self.unpersist(filename)


    def save(self, filename):
        """
        _save_
        
        This just maps to persist
        """

        self.persist(filename)


    def getOutputModule(self, step, outputModule):
        """
        _getOutputModule_
        
        Get the output module from a particular step
        """

        stepReport = self.retrieveStep(step = step)

        if not stepReport:
            return None

        return getattr(stepReport.output, outputModule, None)


    def getOutputFile(self, fileName, outputModule, step):
        """
        _getOutputFile_

        Takes a fileRef object and returns a DataStructs/File object as output
        """

        outputMod = self.getOutputModule(step = step, outputModule = outputModule)

        if not outputMod:
            return None

        fileRef = getattr(outputMod.files, fileName, None)

        file = File()

        #Now we fill it, one piece at a time
        keyList = fileRef.listSections_()

        #Locations
        file.setLocation(fileRef.locations)
        keyList.remove('locations')

        #Runs
        runList = fileRef.runs.listSections_()
        for run in runList:
            lumis  = getattr(fileRef.runs, run)
            newRun = Run(run, *lumis)
            file.addRun(newRun)
        keyList.remove('runs')


        # And now, datasets
        dataDict = {}
        for var in outputMod.dataset.listSections_():
            dataDict[var] = getattr(outputMod.dataset, var)
        file['dataset'] = dataDict

        for entry in keyList:
            file[entry] = getattr(fileRef, entry)

        #Variables to be added
        file['ModuleLabel'] = outputModule 


        return file

        


    def getFilesFromOutputModule(self, step, outputModule):
        """
        _getFilesFromOutputModule_
        
        Grab all the files in a particular output module
        """

        listOfFiles = []

        outputMod = self.getOutputModule(step = step, outputModule = outputModule)

        if not outputMod:
            return None

        for n in range(outputMod.files.fileCount):
            file = self.getOutputFile(fileName = 'file%i' %(n), outputModule = outputModule, step = step)
            if not file:
                msg = "Could not find file%i in module" %(n)
                logging.error(msg)
                return None
            
            #Now, append to the list of files
            listOfFiles.append(file)

        return listOfFiles


    def getAllFilesFromStep(self, step):
        """
        _getAllFilesFromStep_
        
        For a given step, retrieve all the associated files
        """

        stepReport = self.retrieveStep(step = step)

        if not stepReport:
            return None

        listOfModules = getattr(stepReport, 'outputModules', None)

        if not listOfModules:
            return None

        listOfFiles = []

        for module in listOfModules:
            tmpList = self.getFilesFromOutputModule(step = step, outputModule = module)
            if not tmpList:
                return None
            listOfFiles.extend(tmpList)


        return listOfFiles


    def getAllFiles(self):
        """
        _getAllFiles_

        Grabs all files in all output modules in all steps
        """

        listOfFiles = []

        for step in self.data.steps:
            tmp = self.getAllFilesFromStep(step = step)
            if not tmp:
                return None
            listOfFiles.extend(tmp)



        return listOfFiles




        

        

