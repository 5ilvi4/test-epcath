import copy
import random
from Schedule import *
from operator import itemgetter

############################################################################################################################################################################################################ 
######################################### BEGIN TIME PERIOD DATA TYPE ###################################################################################################################################### 
############################################################################################################################################################################################################ 

class TimePeriod:
    '''
    Class to model a given time period of scheduling.
        
    '''
    def __init__(self, params):
        
        CathRooms = {(d,params.cathID,i):Schedule(int(params.resolution),params.labStartTime,params.labEndTime) for i in range(params.numCathRooms) for d in range(params.daysInPeriod)}
        EPRooms = {(d,params.epID,i):Schedule(int(params.resolution),params.labStartTime,params.labEndTime) for i in range(params.numEPRooms) for d in range(params.daysInPeriod)}
        MiddleRooms = {(d,params.middleID,i):Schedule(int(params.resolution),params.labStartTime,params.labEndTime) for i in range(params.numMiddleRooms) for d in range(params.daysInPeriod)}
        DayShifts = {d: ShiftSchedule(params.numCathRooms,params.numEPRooms,params.secondShiftStart) for d in range(params.daysInPeriod)}
        rooms = dict(list(CathRooms.items()) + list(EPRooms.items()) + list(MiddleRooms.items()))
        overflow = {d:[] for d in range(params.daysInPeriod)}
        multiple = 60.0/params.resolution
        holdingBays = {(d,1.0*i):0 for i in range(0,int(params.HBCloseTime*multiple)) for d in range(params.daysInPeriod)}

        self.bins = [copy.deepcopy(rooms),copy.deepcopy(overflow),copy.deepcopy(holdingBays), copy.deepcopy(DayShifts)]

        self.numCathRooms = params.numCathRooms            #Now equivalent to numRooms[cathID]
        self.numEPRooms = params.numEPRooms                #Now equivalent to numRooms[epID]
        self.numMiddleRooms = params.numMiddleRooms        #Now equivalent to numRooms[middleID]        self.numCathRooms = numCathRooms
        self.numRooms = {params.cathID: params.numCathRooms, params.epID:params.numEPRooms, params.middleID:params.numMiddleRooms}   #Added to call as a variable
        self.numRestrictedCath = params.numRestrictedCath
        self.numRestrictedEP = params.numRestrictedEP
        self.numDays = params.daysInPeriod
        self.numWeeks = params.daysInPeriod/5
        self.labStartTime = params.labStartTime
        
        # statistical counters
        self.numTotalProcs = 0
        self.numSameDays = 0
        self.numSameWeeks = 0
        self.numEmergencies = 0
        
        self.numTotalShifts = 0
        self.numFullShifts = 0
        self.numHalfShifts = 0
        self.numQuarterShifts = 0
        
        self.procsPlaced = 0
        self.procsPlacedData = []
        self.primeTimeProcs = 0
        self.primeTimeProcsData = []
        
        self.crossOverProcs = 0
        self.cathToEP = 0           # procedures historically done in Cath that are scheduled in an EP room
        self.epToCath = 0           # procedures historically done in EP that are scheduled in a Cath room
        
        self.overflowCath = 0
        self.overflowEP = 0
        self.overflowMiddle = 0
        self.overflowQuarter = 0
        self.overflowHalf = 0
        self.overflowFull = 0
        self.overflowDays = []

    ######################################################################################################
    ###################################### PHASE ONE: SHIFT SCHEDULING ###################################
    ######################################################################################################


    ################################### SHIFT SCHEDULING FOR ##################################
    #################################### WHOLE TIME PERIOD ####################################
    def packShifts(self,shifts, params):
        '''
        Schedules shifts for the entire time period.
        
        Input: procedures (a list of cleaned procedure data for a given period of time)
                algType (a string describing the type of scheduling algorithm to run)
        Returns: none
        '''
        
        allShifts = copy.deepcopy(shifts)

        # make any room value changes
        for change in params.roomValueChanges:
            shiftType, newRoomValue = change
            for shift in allShifts:
                if shift[params.iShiftType] == shiftType:
                    shift[params.iRoomS] = newRoomValue
        
        # break shifts up by block size horizon
        FullShifts = [p for p in allShifts if p[params.iShiftType] == params.fullShiftID]
        HalfShifts = [p for p in allShifts if p[params.iShiftType] == params.halfShiftID]
        QuarterShifts = [p for p in allShifts if p[params.iShiftType] == params.quarterShiftID]

        self.numTotalShifts = len(FullShifts)+len(HalfShifts)+len(QuarterShifts)
        self.numFullShifts = len(FullShifts)
        self.numHalfShifts = len(HalfShifts)
        self.numQuarterShifts = len(QuarterShifts)
        
        #for d in range(1,timePeriod.numDays+1):
        for d in range(1,self.numDays+1):
            daysShifts = [shift for shift in allShifts if shift[params.iDayS]==d]
            # shifts sorted in descending order
            daysSortedShifts = self.sortShifts(daysShifts, params)
            self.packShiftsForDay(d-1,daysSortedShifts, params)
        


    ###################################### DAY BY DAY SHIFT  ##################################
    ################################# SCHEDULING FOR BOTH LABS ################################
    def packShiftsForDay(self,day,daysShifts, params):
        '''
        Schedules shifts during a given day. Keeps track of overflow shifts
        (that couldn't fit into prime time that day).
        
        Input: day (integer day of time period to be scheduled, indexed from 0)
               daysProcedures given by three lists each containing a type of shift 
               (a list of procedure data for a given day)
        Returns: none
        '''
        shifts = copy.deepcopy(daysShifts)
        shiftsCrossOver = []        
        shiftsOverflow = []
        
        for shiftToPlace in shifts:
            if not self.tryPlaceShift(shiftToPlace,day, params):
                if params.restrictRooms:
                    if shiftToPlace[params.iRoomS] == 2.0:
                        shiftsCrossOver.append(shiftToPlace)
                    else:
                        shiftsOverflow.append(shiftToPlace)
                else:
                    shiftsCrossOver.append(shiftToPlace)
                    
        for shiftToPlace in shiftsCrossOver:
            if not self.tryPlaceShiftInOtherLab(shiftToPlace,day, params):
                shiftsOverflow.append(shiftToPlace)
        
        cathOverflow = [shift for shift in shiftsOverflow if shift[params.iLabS] == 0.0]
        epOverflow = [shift for shift in shiftsOverflow if shift[params.iLabS] == 1.0]
        
        for cathShift in cathOverflow:
            self.placeShiftInLab(cathShift,day, params)
        for epShift in epOverflow:
            self.placeShiftInLab(epShift,day, params)
            
    def tryPlaceShift(self,shift,day,params):
        '''
        Tries to pack each shift into one of the room days of the given day. 
        When packing calls to nextOpenRoomInLab so that each shift will be placed 
        in the lowest numbered room that has space for it 
        
        Input: The day, the shift to be scheduled.
        Notice, the shifts will be passed to this in the order of the labs (Cath, EP) 
        and the reverse order of the legnths of thes shift (1 - full, 0.5 - half, 0.25 - quarter), 
        from which we subtract 0.01 for comparison precision purposes
        Returns: True if the shift was placed, otherwise False
        '''
        
        allShifts = self.bins[3]

        ### STEP 1: get procedure information ###
        toPlace = copy.deepcopy(shift)
        labTo = shift[params.iLabS]
        shiftType = shift[params.iShiftType]
        
        ### STEP 2: place procedure in its own lab in the lowest room number possible if there is room for it ###    
        if allShifts[day].maxOpenRoomInLab(labTo) >= shiftType:
            firstOpen = allShifts[day].nextOpenRoomInLab(labTo, shiftType)
            allShifts[day].placeProvider(
                labTo,firstOpen,toPlace[params.iProviderS],toPlace[params.iShiftType],toPlace[params.iShiftLength],toPlace[params.iLabS]
            )
            return True
        return False

    
    def tryPlaceShiftInOtherLab(self,shift,day, params):
        '''
        Tries to pack each shift into one of the room days of other lab in the given day. 
        When packing calls to nextOpenRoomInLab so that each shift will be placed 
        in the lowest numbered room that has space for it 
        
        Input: The day, the shift to be scheduled.
        Notice, the shifts will be passed to this in the order of the labs (Cath, EP) 
        and the reverse order of the legnths of thes shift (1 - full, 0.5 - half, 0.25 - quarter), 
        from which we subtract 0.01 for comparison precision purposes
        Returns: True if the shift was placed, otherwise False
        '''
        
        allShifts = self.bins[3]
    
        ### STEP 1: get procedure information ###
        toPlace = copy.deepcopy(shift)
        originalLab = shift[params.iLabS]
        labTo = params.cathID if originalLab==params.epID else params.epID
        shiftType = shift[params.iShiftType]
        maxRoomAllowed = params.cathCrossOverRooms-1 if labTo==params.cathID else params.epCrossOverRooms-1
    
        ### STEP 2: Place procedure in the other lab in the lowest room number possible if there is room for it ###    
        if allShifts[day].maxOpenRoomInLab(labTo) >= shiftType:
            firstOpen = allShifts[day].nextOpenRoomInLab(labTo, shiftType)
            if firstOpen > maxRoomAllowed:
                return False
            allShifts[day].placeProvider(
                labTo, firstOpen, 
                toPlace[params.iProviderS], 
                toPlace[params.iShiftType], 
                toPlace[params.iShiftLength],
                toPlace[params.iLabS]
            )
            return True
        return False

          
    def placeShiftInLab(self,shift,day, params):
        '''
        Packs each shift into the room in its lab which has the earliest end time in the given day. 
        
        Input: The day, the shift to be scheduled.
        
        Returns: None
        '''
        allShifts = self.bins[3]
        daysShifts = allShifts[day]
    
        ### STEP 1: get shift information ###
        labTo = shift[params.iLabS]
        roomTo = daysShifts.findEarliestRoom(labTo)[1]
    
        ### STEP 2: Place procedure in the room in its lab which has the earliest end time ###
        daysShifts.placeProvider(
            labTo, 
            roomTo, 
            shift[params.iProviderS], 
            shift[params.iShiftType], 
            shift[params.iShiftLength],
            shift[params.iLabS]
        )
        
        
    ######################################## HELPER FUNCTIONS ########################################
    ####################################### (SHIFT BIN PACKING) ######################################
    #def cmp(x, y): return (x > y) - (x < y)


    def sortShifts(self,shifts, params):
        '''
        Sorts shifts in decreasing order by type (1, 0.5, 0.25)
        
        Input: shifts
        Returns: shifts sorted
        '''
        shifts = copy.deepcopy(shifts)
        #print("before" shifts[1:10])
        sorted(shifts, key=itemgetter(params.iShiftType), reverse=True)
        #shifts.sort(lambda x,y: cmp(x[params.iShiftType],y[params.iShiftType]),reverse=True)
        #print("after" shifts[1:10])
        return shifts
    

    ######################################################################################################
    ######################################## PHASE TWO: PROC PACKING #####################################
    ######################################################################################################

    ##################################### PROC PACKING FOR ####################################
    #################################### WHOLE TIME PERIOD ####################################

    def packProcedures(self,procedures, params):
        '''
        Packs procedures into the appropriate shifts during the time period. Assumes
        that the shifts have already been scheduled.
        
        Input: procedures (a list of cleaned procedure data for a given period of time)
        Returns: none
        '''

        allProcs = procedures[:]

        ###### STEP 0: MODIFY PROCEDURE DATA ACCORDING TO SPECS ######
        # add procedure ID's
        for i in range(len(allProcs)):
            proc = procedures[i]
            proc.append(i)

        if not params.schedMRinHB:
            # change all MR holding bay times to 0
            for proc in allProcs:
                proc[params.iPreTime] = 0.0 if proc[params.iRoom]==3.0 else proc[params.iPreTime]
                proc[params.iPostTime] = 0.0 if proc[params.iRoom]==3.0 else proc[params.iPostTime]

        if params.middleRoomPreRandom and params.schedMRinHB:
            for proc in allProcs:
                preTime = random.gauss(params.desiredPreMeanMR, params.desiredPreStDevMR)
                proc[params.iPreTime] = preTime if proc[params.iRoom]==3.0 else proc[params.iPreTime]

        if params.middleRoomPostRandom and params.schedMRinHB:
            for proc in allProcs:
                postTime = random.gauss(params.desiredPostMeanMR, params.desiredPostStDevMR)
                proc[params.iPostTime] = postTime if proc[params.iRoom]==3.0 else proc[params.iPostTime]

        if params.preProcHBCleanTimeRandom:
            for proc in allProcs:
                cleanTime = random.gauss(params.desiredPreCleanMean, params.desiredPreCleanStDev)
                proc[params.iPreProcHBCleanTime] = cleanTime       
        
        if params.postProcHBCleanTimeRandom:
            for proc in allProcs:
                cleanTime = random.gauss(params.desiredPostCleanMean, params.desiredPostCleanStDev)
                proc[params.iPostProcHBCleanTime] = cleanTime       
        
        if params.postProcRandom:
            # change the post procedure time to a random value from a distribution with a given mean/standard deviation
            for proc in allProcs:
                postTime = random.gauss(params.desiredMean, params.desiredStDev)
                proc[params.iPostTime] = postTime if proc[params.iRoom]!=3.0 else proc[params.iPostTime]
                
        if params.multPostProcTime:
            for proc in allProcs:
                postTime = params.PostProcMult * proc[params.iPostTime]
                proc[params.iPostTime] = postTime            
            
        if params.ConvertPreProcToHours:
            # Convert the pre procedure time to hours
            for proc in allProcs:
                proc[params.iPreTime] = proc[params.iPreTime]/60
                
        if params.CapHBPreProc:
            # Cap the pre procedure time to be be no more than 3 hours
            for proc in allProcs:
                PreTime = min(proc[params.iPreTime],params.HBPreProcCap)
                proc[params.iPreTime] = PreTime
        
        if params.ChangeProviderDays:
            #Make all changes for each tuple
            for proc in allProcs:            
                if proc[params.iProvider] in list(params.providerChanges.keys()):
                    procDOW = (proc[params.iDay]-1)%5
                    change = params.providerChanges[proc[params.iProvider]]
                    fromDay = change[0]
                    toDay = change[1]
                    proc[params.iDay] += (toDay-fromDay) if procDOW==change[0] else 0

        if params.SwapProviderDays:
            #Make all swap for each tuple
            providerDict = {k:[[],[]] for k in list(params.providerSwaps.keys())}            
            for proc in allProcs:
                if proc[params.iProvider] in list(params.providerSwaps.keys()):
                    procDOW = (proc[params.iDay]-1)%5
                    fromDay = params.providerSwaps[proc[params.iProvider]][0]
                    toDay = params.providerSwaps[proc[params.iProvider]][1]
                    if procDOW in (fromDay,toDay):
                        providerDict[proc[params.iProvider]][0].append(proc) if procDOW == fromDay else providerDict[proc[params.iProvider]][1].append(proc)
            for provider in list(params.providerSwaps.keys()):
                swap = providerSwaps[provider]
                fromDay = swap[0]
                toDay = swap[1]
                for proc in providerDict[provider][0]:
                    proc[params.iDay] += (toDay-fromDay)
                for proc in providerDict[provider][1]:
                    proc[params.iDay] += (fromDay-toDay)

        ###### STEP 1: PACK PROCS INTO SHIFTS DAY BY DAY ######
        # update summary stats
        self.numTotalProcs = len(allProcs)
        self.numSameDays = len([x for x in allProcs if x[params.iSchedHorizon]==1.0])
        self.numSameWeeks = len([x for x in allProcs if x[params.iSchedHorizon]==3.0])
        self.numEmergencies = len([x for x in allProcs if x[params.iSchedHorizon]==0.0])

        #for d in range(1,timePeriod.numDays+1):
        for d in range(1,self.numDays+1):
            daysProcs = [proc for proc in allProcs if proc[params.iDay]==d]
            if params.sortProcs:
                # sort procedures based on parameters
                daysProcs = self.sortProcedures(daysProcs, params.sortIndex ,params.sortDescend, params.iProvider)                  
            self.placeDaysProcs(d-1,daysProcs, params)
            

    ################################## DAY BY DAY PROC PACKING ###################################
    ################################## INTO APPROPRIATE SHIFTS ###################################

    def placeDaysProcs(self,day,daysProcs, params):
        '''
        Iterates through the day's procedures, determines which shift each one belongs in,
        and calls self.placeProcInShift(proc) to place
        Input: a list of the days procedures
        Returns: None
        
        use getProviderRoomAssignment which returns 
        (lab, room number, shift length, and the length of shifts scheduled BEFORE the provider)        
        
        '''
        procsToPlace = copy.deepcopy(daysProcs)
        allShifts = self.bins[3]
        allSchedules =self.bins[0]
        daysShifts = allShifts[day]
        
        for toPlace in procsToPlace:
            # middle room procedures: not part of shift schedule
            if toPlace[params.iRoom] == params.middleID:
                middle1,middle2 = (allSchedules[(day,params.middleID,0)], allSchedules[(day,params.middleID,1)])
                middle1Open,middle2Open = (middle1.getNextOpenTimeSlot(params.labStartTime), middle2.getNextOpenTimeSlot(params.labStartTime))
                # decide which middle room to place the procedure in and when
                if isLater(middle1Open,params.labEndTime) and isLater(middle2Open,params.labEndTime):
                    room = middle1 if isEarlier(middle1Open,middle2Open) else middle1
                else:
                    room = middle2 if isLater(middle1Open,params.labEndTime) else middle1
                when = middle1Open if room == middle1 else middle2Open
                room.scheduleProcedure(toPlace,toPlace[params.iProcTime],when)
                
                # update summary stats
                self.updateHoldingBays(toPlace,day,when, params)
                self.updateProcsPlacedStats(toPlace)
                if isEarlier(when,params.labEndTime):
                    self.updatePrimeTimeProcsStats(toPlace)
                
            # normal procedures: part of shifts
            else:
                providerToPlace = toPlace[params.iProvider]
                shiftInfo = daysShifts.getProviderRoomAssignment(providerToPlace)
                labToPlace = shiftInfo[0]           
                roomToPlace = shiftInfo[1]
                # determine when the procedure's corresponding shift starts
                providerStart = daysShifts.getProviderStartTime(labToPlace,roomToPlace,providerToPlace)                
                daysSchedule = allSchedules[(day,labToPlace,roomToPlace)]
                # determine when the procedure should start
                whenToPlace = daysSchedule.getNextOpenTimeSlot(providerStart)
                daysSchedule.scheduleProcedure(toPlace,toPlace[params.iProcTime],whenToPlace)

                # update summary stats
                self.updateHoldingBays(toPlace,day,whenToPlace, params)
                self.updateProcsPlacedStats(toPlace)
                self.updateCrossoverStats(toPlace,labToPlace, params)
                if isLater(whenToPlace,params.labEndTime):
                    self.updateOverflowStats(toPlace,shiftInfo[2],day, params)
                else:
                    self.updatePrimeTimeProcsStats(toPlace)


    ######################################## HELPER FUNCTIONS ########################################
    ######################################### (PROC PACKING) #########################################

    def maxTime(self,time1,time2):
        '''
        Determines the later time.
        Input: time1 and time2 to compare, in the form (hours,minutes)
        Returns: the later time. If they are the same time, returns it.
        '''
        hour1,min1 = time1
        hour2,min2 = time2

        if hour1 < hour2:
            return time2
        elif hour1 > hour2:
            return time1
        else:
            if min1 < min2:
                return time2
            else:
                return time1

    def sortProcedures(self,procs,index,descending,iProvider):
        '''
        Sort the procedures based on their procedure time, in either ascending or descending order.
        Input: procs (list of procedure data to sort)
               index (the index of the procedure attribute to sort based on)
               descending (bool value indicating whether the sorted order
               should be descending, i.e. longest first, or not)
        Returns: a sorted copy of the procs list
        '''
        procsCopy = procs[:]
        procsCopy.sort(key=lambda x:(x[iProvider],x[index]),reverse=descending)
        return procsCopy


    def updateHoldingBays(self,procedure,day,procStartTime, params):
        '''
        '''
        # add counters to holding bay
        # Computes the start time of each procedure as number of hours into the day.
        # Patients who spent less than 15 minutes recovering do not go to the holding bay since we assume this is flawed data
        if procedure[params.iPostTime]> params.MinHBTime:
            procStartTime = minutesFromTimeFormatted(procStartTime)/60.0
            preHoldingStart = procStartTime - procedure[params.iPreTime]
            preProcClean = procStartTime + procedure[params.iPreProcHBCleanTime]
            postHoldingStart = procStartTime + procedure[params.iProcTimeMinusTO]/60.0
            postHoldingEnd = postHoldingStart + procedure[params.iPostTime]
            postHoldingClean = postHoldingEnd + procedure[params.iPostProcHBCleanTime]

            # multipliers to round up/down to nearest resolution
            preHoldingStartRound = ((60*preHoldingStart)//params.resolution)
            preHoldingEndRound = ((60*preProcClean)//params.resolution)
            postHoldingStartRound = ((60*postHoldingStart)//params.resolution)
            postHoldingEndRound = ((60*postHoldingClean)//params.resolution)          

            numPreSlots = preHoldingEndRound-preHoldingStartRound
            numPostSlots = postHoldingEndRound-postHoldingStartRound

            for i in range(int(numPreSlots)):
                self.bins[2][(day,preHoldingStartRound+i)] += 1
            
            for j in range(int(numPostSlots)):
                self.bins[2][(day,postHoldingStartRound+j)] += 1


    def updateOverflowStats(self,procOverflow,shiftType,day, params):
        if procOverflow[params.iRoom] == 3.0:
            self.overflowMiddle += 1
        elif procOverflow[params.iLab] == cathID:
            self.overflowCath += 1
        elif procOverflow[params.iLab] == epID:
            self.overflowEP += 1

        if shiftType == 0.25:
            self.overflowQuarter += 1
        elif shiftType == 0.5:
            self.overflowHalf += 1
        elif shiftType == 1.0:
            self.overflowFull += 1

        self.overflowDays.append(day) if day not in self.overflowDays else None

    def updateProcsPlacedStats(self,procedure):
        self.procsPlaced += 1
        self.procsPlacedData.append(procedure)

    def updatePrimeTimeProcsStats(self,procedure):
        self.primeTimeProcs += 1
        self.primeTimeProcsData.append(procedure)

    def updateCrossoverStats(self,procedure,placedLabID, params):
        originalLab = procedure[params.iLab]
        if originalLab != placedLabID:
            self.crossOverProcs += 1
            if originalLab == params.cathID:
                self.cathToEP += 1
            else:
                self.epToCath += 1


    ######################################################################################################
    ###################################### PHASE THREE: SUMMARY STATS ####################################
    ######################################################################################################

    def getUtilizationStatistics(self, params):
        '''

        '''  
        CathRooms = {(d,params.cathID,i):[] for i in range(params.numCathRooms) for d in range(self.numDays)}
        EPRooms = {(d,params.epID,i):[] for i in range(params.numEPRooms) for d in range(self.numDays)}
        roomsUtil = dict(list(CathRooms.items()) + list(EPRooms.items()))

        for day in range(self.numDays):
            for c in range(params.numCathRooms):
                roomMinutes = self.bins[0][(day,params.cathID,c)].getTotalPrimeTimeMinutes()
                util = roomMinutes / params.totalTimeRoom
                roomsUtil[(day,params.cathID,c)] = util
            for e in range(params.numEPRooms):
                roomMinutes = self.bins[0][(day,params.epID,e)].getTotalPrimeTimeMinutes()
                util = roomMinutes / params.totalTimeRoom
                roomsUtil[(day,epID,e)] = util

        avgDays = self.getAverageUtilizationByDay(roomsUtil, params)
        avgsCath = [avgDays[x] for x in list(avgDays.keys()) if x[1]==params.cathID]
        avgsEP = [avgDays[x] for x in list(avgDays.keys()) if x[1]==params.epID]
        cathAverage = sum(avgsCath)/self.numDays
        epAverage = sum(avgsEP)/self.numDays

        avgDaysCombined = [[avgDays[(d,params.cathID)],avgDays[(d,params.epID)]] for d in range(self.numDays)]
        avgWeeks = self.getAverageUtilizationByWeek(avgDaysCombined)
                
        return (cathAverage,epAverage,avgDaysCombined,avgWeeks,roomsUtil)

    def getAverageUtilizationByDay(self,daysUtil, params):
        '''

        '''
        daysUtilCopy = copy.deepcopy(daysUtil)
        daysAverageUtil = {}
        
        for d in range(self.numDays):
            cathDayTotal = 0
            epDayTotal = 0
            for c in range(self.numCathRooms):
                cathDayTotal += daysUtilCopy[(d,params.cathID,c)]
            for e in range(self.numEPRooms):
                epDayTotal += daysUtilCopy[(d,params.epID,e)]
            daysAverageUtil[(d,cathID)] = (cathDayTotal/self.numCathRooms)
            daysAverageUtil[(d,epID)] = (epDayTotal/self.numEPRooms)

        return daysAverageUtil           

    def getAverageUtilizationByWeek(self,avgDays):
        '''
        '''
        avgDaysCopy = copy.deepcopy(avgDays)
        weeksUtil = [[avgDaysCopy[i],avgDaysCopy[i+1],avgDaysCopy[i+2],avgDaysCopy[i+3],avgDaysCopy[i+4]] for i in range(0,self.numDays-4,5)]
        weeksAverageUtil = [[] for i in range(int(self.numWeeks))] #Cindie Edit/Check this
        #weeksAverageUtil = [[] for i in range(self.numWeeks)] #orig

        #for w in range(self.numWeeks): #orig
        for w in range(int(self.numWeeks)):
            cathWeekTotal = 0
            epWeekTotal = 0
            week = weeksUtil[w]
            for d in range(5):
                cathWeekTotal += week[d][0]
                epWeekTotal += week[d][1]
            weeksAverageUtil[w].append(cathWeekTotal/5)
            weeksAverageUtil[w].append(epWeekTotal/5)
            
        return weeksAverageUtil
        

    def getProcsByMinuteVolume(self,allProcs, params):
        '''
        '''
        emergencies = [x for x in allProcs if x[params.iSchedHorizon] == 1.0]
        sameDay = [x for x in allProcs if x[params.iSchedHorizon]==2.0]
        sameWeek = [x for x in allProcs if x[params.iSchedHorizon]==3.0]

        emergFlex = [x for x in emergencies if x[params.iRoom]==2.0]
        emergFlexMin = sum(x[params.iProcTime] for x in emergFlex)
        emergInflex = [x for x in emergencies if x[params.iRoom]!=2.0]
        emergInflexMin = sum(x[params.iProcTime] for x in emergInflex)

        sameDayFlex = [x for x in sameDay if x[params.iRoom]==2.0]
        sameDayFlexMin = sum(x[params.iProcTime] for x in sameDayFlex)
        sameDayInflex = [x for x in sameDay if x[params.iRoom]!=2.0]
        sameDayInflexMin = sum(x[params.iProcTime] for x in sameDayInflex)

        sameWeekFlex = [x for x in sameWeek if x[params.iRoom]==2.0]
        sameWeekFlexMin = sum(x[params.iProcTime] for x in sameWeekFlex)
        sameWeekInflex = [x for x in sameWeek if x[params.iRoom]!=2.0]
        sameWeekInflexMin = sum(x[params.iProcTime] for x in sameWeekInflex)

        return [emergFlexMin,emergInflexMin,sameDayFlexMin,sameDayInflexMin,sameWeekFlexMin,sameWeekInflexMin]

                        

#####################################################################################################
##################################### END TIME PERIOD DATA TYPE #####################################
#####################################################################################################
