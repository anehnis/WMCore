#!/usr/bin/env python
"""
_Job_

A job is owned by a jobgroup (which gives it it's workflow) and is 
associated to a (set of) file(s). The job interacts with its jobgroup
to acquire/complete/fail files. A job know's it's Workflow via it's 
jobgroup. A job is meaningless without a jobgroup.

A WMBS job != a job in a batch system, it's more abstract - it's the piece of 
work that needs to get done.

Jobs are added to the WMBS database by their parent JobGroup, but are 
responsible for updating their state (and name).
"""

__revision__ = "$Id: Job.py,v 1.30 2009/07/10 20:04:22 mnorman Exp $"
__version__ = "$Revision: 1.30 $"

import datetime
from sets import Set

from WMCore.DataStructs.Job import Job as WMJob
from WMCore.DataStructs.Fileset import Fileset
from WMCore.WMBS.File import File
from WMCore.WMBS.Fileset import Fileset as WMBSFileset
from WMCore.WMBS.WMBSBase import WMBSBase
from WMCore.Services.UUID import makeUUID

class Job(WMBSBase, WMJob):
    """
    A job in WMBS
    """
    def __init__(self, name = None, files = None, id = None):
        """
        ___init___
        
        jobgroup object is used to determine the workflow. 
        inputFiles is a list of files that the job will process.
        """
        WMBSBase.__init__(self)
        WMJob.__init__(self, name = name, files = files)

        self["id"] = id
        self["jobgroup"] = None
        self["couch_record"] = None
        self["attachments"] = {}

        return
            
    def create(self, group):
        """
        _create_
        
        Write the job to the database.
        """
        if self["id"] != None:
            return

        existingTransaction = self.beginTransaction()

        self["jobgroup"] = group.id

        if self["name"] == None:
            self["name"] = makeUUID()

        jobAction = self.daofactory(classname = "Jobs.New")
        jobAction.execute(self["jobgroup"], self["name"], self["couch_record"],
                          self["location"], conn = self.getDBConn(),
                          transaction = self.existingTransaction())

        self.exists()

        maskAction = self.daofactory(classname = "Masks.New")
        maskAction.execute(jobid = self["id"], conn = self.getDBConn(),
                           transaction = self.existingTransaction())

        self.associateFiles()
        self.commitTransaction(existingTransaction)
        return
        
    def delete(self):
        """
        Remove a job from WMBS
        """
        deleteAction = self.daofactory(classname = "Jobs.Delete")
        deleteAction.execute(id = self["id"], conn = self.getDBConn(),
                              transaction = self.existingTransaction())
        return

    def save(self):
        """
        _save_

        Flush all changes that have been made to the job to the database.
        """
        existingTransaction = self.beginTransaction()

        saveAction = self.daofactory(classname = "Jobs.Save")
        saveAction.execute(self["id"], self["jobgroup"], self["name"],
                           self["couch_record"], self["location"], 
                           self["outcome"], conn = self.getDBConn(),
                           transaction = self.existingTransaction())

        maskAction = self.daofactory(classname = "Masks.Save")
        maskAction.execute(jobid = self["id"], mask = self["mask"],
                           conn = self.getDBConn(),
                           transaction = self.existingTransaction())

        self.associateFiles()
        self.commitTransaction(existingTransaction)
        return

    def exists(self):
        """
        _exists_

        Does a job exist with this name or id.
        """
        if self["id"] != None:
            action = self.daofactory(classname = "Jobs.ExistsByID")
            result =  action.execute(id = self["id"], conn = self.getDBConn(),
                                     transaction = self.existingTransaction())
        else:
            action = self.daofactory(classname = "Jobs.Exists")
            result = action.execute(name = self["name"], conn = self.getDBConn(),
                                  transaction = self.existingTransaction())

            if result:
                self["id"] = result

        return result
                
    def load(self):
        """
        _load_

        Load the job's name, id, jobgroup, state, state_time, retry_count, 
        couch_record, location and outcome from the database.  Either the ID
        or the name must be set before this is called.
        """
        if self["id"] != None:
            loadAction = self.daofactory(classname = "Jobs.LoadFromID")
            results = loadAction.execute(self["id"], conn = self.getDBConn(),
                                         transaction = self.existingTransaction())
        else:
            loadAction = self.daofactory(classname = "Jobs.LoadFromName")
            results = loadAction.execute(self["name"], conn = self.getDBConn(),
                                         transaction = self.existingTransaction())

        self.update(results)
        return

    def loadData(self):
        """
        _loadData_

        Load all information about the job, including the mask and all input
        files.  Either the ID or the name must be specified before this is
        called.
        """
        existingTransaction = self.beginTransaction()
        
        self.load()
        self.getMask()
        
        fileAction = self.daofactory(classname = "Jobs.LoadFiles")
        files = fileAction.execute(self["id"], conn = self.getDBConn(),
                                   transaction = self.existingTransaction())

        self["input_files"] = []
        for file in files:
            newFile = File(id = file["id"])
            newFile.loadData(parentage = 0)
            self.addFile(newFile)

        self.commitTransaction(existingTransaction)
        return
    
    def getMask(self):
        """
        _getMask_
        
        Load the job mask from the database and return it.
        """
        jobMaskAction = self.daofactory(classname = "Masks.Load")
        jobMask = jobMaskAction.execute(self["id"], conn = self.getDBConn(),
                                        transaction = self.existingTransaction())

        self["mask"].update(jobMask)
        return self["mask"]
    
    def getFiles(self, type = "list"):
        """
        _getFiles_

        Retrieve a list of files that are associated with the job.
        """
        if self["id"] == None:
            return WMJob.getFiles(self, type)
    
        existingTransaction = self.beginTransaction()
        idAction = self.daofactory(classname = "Jobs.LoadFiles")
        fileIDs = idAction.execute(self["id"], conn = self.getDBConn(),
                                   transaction = self.existingTransaction())

        currentFileIDs = WMJob.getFiles(self, type = "id") 
        for fileID in fileIDs:
            if fileID["id"] not in currentFileIDs:
                self.loadData()
                break

        self.commitTransaction(existingTransaction)
        return WMJob.getFiles(self, type)

    def associateFiles(self):
        """
        _associateFiles_
        
        Update the wmbs_job_assoc table with the files in the inputFiles for the
        job.
        """
        files = WMJob.getFiles(self, type = "id")

        if len(files) > 0:
            addAction = self.daofactory(classname = "Jobs.AddFiles")
            addAction.execute(self["id"], files, conn = self.getDBConn(),
                              transaction = self.existingTransaction())

        return


    def getState(self):
        """
        _getState_

        Retrieve the state that the job is currently in.

        """

        action = self.daofactory(classname = "Jobs.GetState")
        state = action.execute(self["id"], conn = self.getDBConn(), transaction = self.existingTransaction)

        return state
