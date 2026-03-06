'''
Adapted from @nicseo code 11/20/14

Last Modified: 1/5/2026

@author: cindiewu
'''

import csv
import os
import math
import copy
import random
from types import SimpleNamespace

import pandas
import matplotlib.pyplot as plt

from IPython.display import display

from Schedule import *
from ShiftSchedule import *
from Utilities import *
from DataProcessor import *
from Params import *
from TimePeriod import *

from CostAnalysis import (
    HoldingBayCostParams,
    CloseTimeCostParams,
    summarize_hb_decision,
    summarize_close_time_decision,
)

import VisualizationAnalysis as VA


#set directory
#os.chdir("/home/matrix/")
os.chdir("/content/test-epcath/")



######################################################################################################
######################################################################################################
##################################### READING/PROCESSING METHODS #####################################
######################################################################################################
######################################################################################################    

def readShiftData(fileName, numEntries):
    '''
    Reads shift data from csv.

    Input:
        fileName: path to shift csv
        numEntries: last column index to read (inclusive style used in old code)

    Returns:
        list of shift rows as floats
    '''
    shifts = []
    with open(fileName, 'r') as f:
        reader = csv.reader(f)
        for row in reader:
            row = [float(i) for i in row[:numEntries+1]]
            shifts.append(row)
    return shifts

def readProcData(fileName, numEntries):
    '''
    Input: fileName (string name of the file you want to process procedural data from

    Returns: a list of lists, each one being one procedure's information stored as floats
    '''
    procedures = []
    with open(fileName, 'r') as f:
        reader = csv.reader(f)
        for row in reader:
            row = [float(i) for i in row[:numEntries+1]]
            procedures.append(row)
    return procedures

def cleanProcTimes(allProcs, iProcTime, turnover, totalTimeRoom):
    '''
    Input: allProcs (list of all procedures as processed from csv)
    
    Returns: list of all procedures modified so that no procedure is
                of length zero, and procedures of length greater than
                totalTimeRoom are truncated
    '''
    newProcs = allProcs[:]

    for i in range (len(newProcs)):
        procTime = newProcs[i][iProcTime]
        procTime += turnover
        if procTime > totalTimeRoom:
            procTime = totalTimeRoom
        newProcs[i][iProcTime] = procTime
    return newProcs

def saveSchedulingResults(timePeriod,workbook,readable):

    out = open(workbook,'w', encoding='utf-8')
    writer = csv.writer(out)

    days = timePeriod.numDays
    roomDays = timePeriod.bins[0]
    roomShifts = timePeriod.bins[3]
    allTimes = roomDays[(0,0.0,0)].timeSlots.keys()
    times = [x for x in allTimes if isLater(x,(6,45))]
    times.sort(key=lambda x: (x[0],x[1]))
    
    # initialize column names
    maxShifts = getMaxShifts(timePeriod)
    columns = ['Day','Lab','Room']
    if readable:
        columns.append('Shifts')
    else:
        columns = ['Day','Lab','Room']
        for i in range(1,maxShifts+1):
            shift = 'Shift '+str(i)
            columns += [shift+' Start', shift+' ProviderKey', shift+' Type', shift+' Original Lab', shift+' Original Start', shift+' Original AM/PM']
    for time in times:
        columns.append(time)
    writer.writerow(columns)

    # write row data: each row represents a room day schedule
    data = []
    ###################################################################################################################
    def generateRowData(day,numRooms,labName,labID):
        for room in range(numRooms):
            dayInfo = [str(d),labName,room]
            # extract shift info
            shifts = roomShifts[day-1].rooms[(labID,room)]
            if readable:
                dayInfo.append(["Start: "+str(x[3])+", Prov: "+str(int(x[0]))+", Shift: "+str(x[1]) for x in shifts])
            else:
                for i in range(maxShifts):
                    try:
                        shift = shifts[i]
                        dayInfo += [minutesFromTimeFormatted(shift[3])/60.0,int(shift[0]),shift[1],shift[4],'-','-']
                    except IndexError:
                        dayInfo += ['','','','','','']
            # extract schedule info
            s = roomDays[(day-1,labID,room)]
            seen = set()
            for t in times:
                procs = s.timeSlots[t]
                if len(procs) != 0:
                    proc = s.timeSlots[t][0]
                    procID = proc[ID]
                    if procID not in seen:
                        seen.add(procID)
                        dayInfo.append("Proc "+str(proc[ID])+": "+
                                   str(int(proc[iProcTime]))+
                                   " min, Prov: "+str(int(proc[iProvider]))) if readable else dayInfo.append(proc[ID])
                    else:
                        dayInfo.append(proc[ID])
            data.append(dayInfo)
    ###################################################################################################################
    for d in range(1,days+1):
        # Cath room schedules
        generateRowData(d,numCathRooms,'Cath',cathID)
        # EP room schedules
        generateRowData(d,numEPRooms,'EP',epID)
    writer.writerows(data)
    
    
def getMaxShifts(timePeriod):
    allShifts = timePeriod.bins[3]
    days = timePeriod.numDays
    maximum = 0
    for d in range(0,days):
        for cath in range(numCathRooms):
            shifts = allShifts[d].rooms[(cathID,cath)]
            if len(shifts) > maximum:
                maximum = len(shifts)
        for ep in range(numEPRooms):
            shifts = allShifts[d].rooms[(epID,ep)]
            if len(shifts) > maximum:
                maximum = len(shifts)
    return maximum
    

def saveHoldingBayResults(timePeriod,workbook, params):

    out = open(workbook,'w', encoding='utf-8')
    writer = csv.writer(out)

    multiple = 60.0/params.resolution
    times = [i for i in range(int(params.HBCloseTime*multiple))]
    columns = ["Day"]
    for time in times:
        hours = math.floor(time/multiple)
        minutes = (time - hours*multiple)*params.resolution
        columns.append(str(int(hours))+":"+str(format(int(minutes), '02d')))
    writer.writerow(columns)
    
    data = []
    for d in range(timePeriod.numDays):
        holdingBays = timePeriod.bins[2]
        day = [holdingBays[(d,time)] for time in times]
        day.insert(0,str(d+1))
        data.append(day)

    writer.writerows(data)

def printOutputStatistics(timePeriod, procedures, params):
    print("\n...Done!")
    
    print("\n*********PARAMETERS*********")
    print("Procedure Sorting Priority: " + str(params.wSortPriority.value))
    print("\tsortProcs: " + str(params.sortProcs))
    print("\tsortIndex: " + str(params.sortIndex))
    print("\tsortDescend: " + str(params.sortDescend))
    print("Scenario: " + str(params.wFiles.value))
    print("\tprocDataFile: " + str(params.procDataFile))
    print("\tshiftDataFile: " + str(params.shiftDataFile))
    print("Mean HB Cleaning Time (hours): " + str(params.desiredPreCleanMean))
    print("Resolution (minutes): " + str(params.resolution))
    
    print("Cath rooms: "+str(params.numCathRooms))
    print("EP rooms: "+str(params.numEPRooms))
    print("Post procedure determination random? "+str(params.postProcRandom))
    print("Pre procedure time converted to hours? "+str(params.ConvertPreProcToHours))
    print("Change provider days? "+str(params.ChangeProviderDays))
    print("Swap provider days? "+str(params.SwapProviderDays))
    print("Pre procedure cap implemented? "+str(params.CapHBPreProc))

    print("\n*********PROCEDURE DATA*********")
    print("Total procedures: "+str(timePeriod.numTotalProcs))
    print("Same days: "+str(timePeriod.numSameDays))
    print("Same weeks: "+str(timePeriod.numSameWeeks))
    print("Emergencies: "+str(timePeriod.numEmergencies))
    minutes = timePeriod.getProcsByMinuteVolume(procedures, params)
    for x in range(6):
        minutes[x] = round(minutes[x],2)
    print("\tBREAKDOWN BY MINUTES")
    print("\tSame week flex: "+str(minutes[4])+" minutes")
    print("\tSame week inflex: "+str(minutes[5])+" minutes")
    print("\tSame day flex: "+str(minutes[2])+" minutes")
    print("\tSame day inflex: "+str(minutes[3])+" minutes")
    print("\tEmergency flex: "+str(minutes[0])+" minutes")
    print("\tEmergency inflex: "+str(minutes[1])+" minutes")

    
    print("\n*********OVERFLOW STATS*********")
    print("Total of "+str(timePeriod.procsPlaced)+" procedures placed")
    print("Total procedures scheduled past closing time: "+str(timePeriod.overflowCath+timePeriod.overflowEP))
    print("\tCath overflow: "+str(timePeriod.overflowCath))
    print("\tEP overflow: "+str(timePeriod.overflowEP))
    print("\t---")
    print("\tQuarter day shift overflows: "+str(timePeriod.overflowQuarter))
    print("\tHalf day shift overflows: "+str(timePeriod.overflowHalf))
    print("\tFull day shift overflows: "+str(timePeriod.overflowFull))
    print("Same day/emergencies overflow during days (0 index): "+str(sorted(timePeriod.overflowDays)))
    
    print("\n*********CROSSOVER STATS*********")
    print("Total number of crossover procedures: "+str(timePeriod.crossOverProcs))
    print("Total number of Cath procedures in EP: "+str(timePeriod.cathToEP))
    print("Total number of EP procedures in Cath: "+str(timePeriod.epToCath))
    
    print("\n*********UTILIZATION STATS*********")
    cath, ep, avgUtilDay, avgUtilWeek, util = timePeriod.getUtilizationStatistics(params)
    print("Average utilization in Cath over time period: "+str(cath))
    print("Average utilization in EP over time period: "+str(ep))
    print("\nType: 'avgUtilDay[_day_]' to view average utilization in Cath and EP on a given day (indexed from 0)")
    print("Type: 'avgUtilWeek[_week_]' to view average utilization in Cath and EP during a given week (indexed from 0)")
    print("Type: 'printSchedule(_day_,_labID_,_room_)' to see a specific room day schedule (indexed from 0)")

    return avgUtilDay,avgUtilWeek

def printSchedule(day,lab,room):
    rooms = timePeriod.bins[0]
    print("Day: "+str(day)+" Lab: "+str(lab)+" Room: "+str(room))
    if lab != middleID:
        shifts = timePeriod.bins[3]
        daysShifts = shifts[day].rooms[(lab,room)]
        print("Day's Shifts: "+str(daysShifts))
    s = rooms[(day,lab,room)]
    times = s.timeSlots.keys()
    times.sort(key=lambda x:(x[0],x[1]))
    seen = set()
    for t in times:
        if t[1]%30 == 0:
            procs = s.timeSlots[t]
            if len(procs) != 0:
                procID = s.timeSlots[t][0][10]
                if procID not in seen:
                    seen.add(procID)
                    print(str(t)+": "+str(s.timeSlots[t][0]))
                else:
                    print(str(t)+": *")                     
            else:
                print(str(t)+": ")



##############################################################################
############# RUNNING OF THE SCRIPT: not necessary to modify #################
##############################################################################

PRIORITY_OPTIONS = [
    'historical',
    'longest procedures first',
    'shortest procedures first',
    'longest recovery time first',
    'shortest recovery time first'
]


def cloneParams(baseParams):
    '''
    Make a lightweight copy of Params without copying widget objects.
    '''
    p = SimpleNamespace()
    skip_keys = {
        'wLbl1', 'wLbl2', 'wLblOptional',
        'wSortPriority', 'wFiles', 'wMeanHBCleanTime', 'wRes', 'wNumCathRooms',
        'button', 'output', 'wAllWidgets'
    }

    for k, v in baseParams.__dict__.items():
        if k in skip_keys:
            continue
        try:
            setattr(p, k, copy.deepcopy(v))
        except Exception:
            setattr(p, k, v)
    return p


def applyPriorityRule(params, priorityName):
    '''
    Set sorting parameters without needing the GUI widgets.
    '''
    if priorityName == 'longest procedures first':
        params.sortProcs = True
        params.sortIndex = params.iProcTime
        params.sortDescend = True
    elif priorityName == 'shortest procedures first':
        params.sortProcs = True
        params.sortIndex = params.iProcTime
        params.sortDescend = False
    elif priorityName == 'longest recovery time first':
        params.sortProcs = True
        params.sortIndex = params.iPostTime
        params.sortDescend = True
    elif priorityName == 'shortest recovery time first':
        params.sortProcs = True
        params.sortIndex = params.iPostTime
        params.sortDescend = False
    else:  # historical
        params.sortProcs = True
        params.sortIndex = params.iHistoricalOrder
        params.sortDescend = False


def percentile(values, pct):
    '''
    Simple percentile helper.
    pct should be in [0, 100].
    '''
    if len(values) == 0:
        return 0
    vals = sorted(values)
    rank = int(math.ceil((pct / 100.0) * len(vals))) - 1
    rank = max(0, min(rank, len(vals) - 1))
    return vals[rank]


def hoursToHHMM(hoursFloat):
    '''
    Convert decimal hours to HH:MM string.
    Example: 18.5 -> "18:30"
    '''
    totalMinutes = int(round(hoursFloat * 60))
    hh = totalMinutes // 60
    mm = totalMinutes % 60
    return str(hh) + ":" + format(mm, '02d')


def getHoldingBayOccupancyMatrix(timePeriod, params):
    '''
    Returns a list of daily occupancy lists.
    Each inner list is occupancy across all holding-bay time buckets for one day.
    '''
    holdingBays = timePeriod.bins[2]
    numSlots = int(params.HBCloseTime * (60.0 / params.resolution))

    allDays = []
    for d in range(timePeriod.numDays):
        occ = [holdingBays[(d, 1.0 * i)] for i in range(numSlots)]
        allDays.append(occ)
    return allDays


def analyzeHoldingBayDemand(timePeriod, params, bayPercentile=95, closePercentile=95):
    '''
    Analyze holding-bay demand profile from simulated occupancy.

    Returns metrics useful for:
    - recommended number of bays
    - recommended close time
    '''
    allDays = getHoldingBayOccupancyMatrix(timePeriod, params)

    dailyPeaks = []
    dailyLastOccupiedHours = []

    for occ in allDays:
        peak = max(occ) if len(occ) > 0 else 0
        dailyPeaks.append(peak)

        occupiedIdx = [i for i, x in enumerate(occ) if x > 0]
        if len(occupiedIdx) == 0:
            dailyLastOccupiedHours.append(0.0)
        else:
            lastIdx = occupiedIdx[-1]
            lastHour = (lastIdx * params.resolution) / 60.0
            dailyLastOccupiedHours.append(lastHour)

    overallPeak = max(dailyPeaks) if len(dailyPeaks) > 0 else 0
    peakP90 = percentile(dailyPeaks, 90)
    peakP95 = percentile(dailyPeaks, bayPercentile)

    lastOccP90 = percentile(dailyLastOccupiedHours, 90)
    lastOccP95 = percentile(dailyLastOccupiedHours, closePercentile)
    overallLast = max(dailyLastOccupiedHours) if len(dailyLastOccupiedHours) > 0 else 0.0

    return {
        "daily_peak_bays": dailyPeaks,
        "daily_last_occupied_hours": dailyLastOccupiedHours,
        "overall_peak_bays": overallPeak,
        "peak_bays_p90": peakP90,
        "peak_bays_p95": peakP95,
        "recommended_bays_p95": int(math.ceil(peakP95)),
        "last_occupied_p90_hours": lastOccP90,
        "last_occupied_p95_hours": lastOccP95,
        "overall_last_occupied_hours": overallLast,
        "recommended_close_p95": hoursToHHMM(lastOccP95),
    }


def evaluateCloseTimeCandidates(timePeriod, params, candidateHours=(17, 18, 19, 20, 21, 22, 23, 24)):
    '''
    Evaluate how much holding-bay demand remains after candidate close times.

    IMPORTANT:
    This measures occupancy remaining after close as a proxy.
    It does NOT yet count exact patient admissions to hospital after close,
    because the current model does not explicitly store patient-level recovery-end events.
    '''
    allDays = getHoldingBayOccupancyMatrix(timePeriod, params)
    slotPerHour = 60.0 / params.resolution

    results = []

    for closeHour in candidateHours:
        closeIdx = int(closeHour * slotPerHour)

        totalSlotsAfterClose = 0
        totalBayHoursAfterClose = 0.0
        daysWithDemandAfterClose = 0

        for occ in allDays:
            after = occ[closeIdx:]
            afterSum = sum(after)
            totalSlotsAfterClose += afterSum

            bayHours = afterSum * (params.resolution / 60.0)
            totalBayHoursAfterClose += bayHours

            if any(x > 0 for x in after):
                daysWithDemandAfterClose += 1

        results.append({
            "close_hour": closeHour,
            "close_time": hoursToHHMM(closeHour),
            "days_with_any_demand_after_close": daysWithDemandAfterClose,
            "total_bay_hours_after_close": totalBayHoursAfterClose,
            "average_bay_hours_after_close_per_day": totalBayHoursAfterClose / float(timePeriod.numDays)
        })

    return results


def buildScenarioSummary(timePeriod, procedures, params, priorityName="unknown"):
    '''
    Collect all metrics needed for planning recommendations.
    '''
    cathUtil, epUtil, avgUtilDay, avgUtilWeek, utilByRoom = timePeriod.getUtilizationStatistics(params)
    hb = analyzeHoldingBayDemand(timePeriod, params)
    closeEval = evaluateCloseTimeCandidates(timePeriod, params)

    summary = {
        "priority_rule": priorityName,
        "total_procs": timePeriod.numTotalProcs,
        "procs_placed": timePeriod.procsPlaced,
        "overflow_total": timePeriod.overflowCath + timePeriod.overflowEP + timePeriod.overflowMiddle,
        "overflow_cath": timePeriod.overflowCath,
        "overflow_ep": timePeriod.overflowEP,
        "overflow_middle": timePeriod.overflowMiddle,
        "crossover_total": timePeriod.crossOverProcs,
        "cath_utilization_avg": cathUtil,
        "ep_utilization_avg": epUtil,
        "mean_room_utilization": (cathUtil + epUtil) / 2.0,
        "holding_bay": hb,
        "close_time_eval": closeEval,
        "avgUtilDay": avgUtilDay,
        "avgUtilWeek": avgUtilWeek,
        "utilByRoom": utilByRoom,
        "timePeriod": timePeriod
    }
    return summary


def printRecommendationReport(summary):
    '''
    Print a concise recommendation report for one scenario.
    '''
    hb = summary["holding_bay"]

    print("\n" + "="*60)
    print("*********PLANNING RECOMMENDATIONS*********")
    print("="*60)
    print("Scheduling priority rule tested: " + str(summary["priority_rule"]))
    print("\n--- HOLDING BAY RECOMMENDATIONS ---")
    print("Recommended holding bays to build (95th percentile daily peak): " + str(hb["recommended_bays_p95"]))
    print("Conservative worst-case peak bays observed: " + str(hb["overall_peak_bays"]))
    print("\n--- CLOSE TIME RECOMMENDATIONS ---")
    print("Recommended holding bay close time (95th percentile last occupied): " + str(hb["recommended_close_p95"]))
    print("Latest observed holding-bay occupancy in simulation: " + str(hoursToHHMM(hb["overall_last_occupied_hours"])))
    print("\n--- UTILIZATION AND OVERFLOW ---")
    print("Average room utilization across Cath and EP: " + str(round(summary["mean_room_utilization"], 4)))
    print("Total procedures placed: " + str(summary["procs_placed"]))
    print("Total procedures scheduled past room closing time: " + str(summary["overflow_total"]))

    print("\n--- CLOSE-TIME SENSITIVITY ANALYSIS ---")
    print("(proxy using bay-hours after close):")
    for row in summary["close_time_eval"]:
        print(
            "  Close @ {0}: days with demand after close = {1}, "
            "total bay-hours after close = {2:.2f}, avg/day = {3:.4f}".format(
                row["close_time"],
                row["days_with_any_demand_after_close"],
                row["total_bay_hours_after_close"],
                row["average_bay_hours_after_close_per_day"]
            )
        )
    print("="*60)


def comparePriorityRules(baseParams, priorities=None, saveResults=False):
    '''
    Run multiple scheduling policies and rank them.

    Ranking logic:
    1. Fewer overflow procedures
    2. Lower 95th percentile holding-bay peak
    3. Earlier 95th percentile last occupied time
    4. Higher average room utilization
    '''
    if priorities is None:
        priorities = PRIORITY_OPTIONS

    results = []

    print("\n" + "="*60)
    print("RUNNING COMPARISON OF SCHEDULING PRIORITY RULES")
    print("="*60)

    for priorityName in priorities:
        print(f"\nTesting: {priorityName}...")
        p = cloneParams(baseParams)
        applyPriorityRule(p, priorityName)

        timePeriod, summary = RunSimulation(
            p,
            saveOutputs=saveResults,
            printStats=False,
            printRecommendations=False
        )

        summary["priority_rule"] = priorityName
        results.append(summary)

    ranked = sorted(
        results,
        key=lambda x: (
            x["overflow_total"],
            x["holding_bay"]["peak_bays_p95"],
            x["holding_bay"]["last_occupied_p95_hours"],
            -x["mean_room_utilization"]
        )
    )

    best = ranked[0]

    print("\n" + "="*60)
    print("COMPARISON RESULTS - RANKED BY PERFORMANCE")
    print("="*60)
    for i, r in enumerate(ranked, 1):
        print(
            "#{0} {1}: overflow={2}, bays_p95={3}, close_p95={4}, mean_util={5:.4f}".format(
                i,
                r["priority_rule"],
                r["overflow_total"],
                r["holding_bay"]["recommended_bays_p95"],
                r["holding_bay"]["recommended_close_p95"],
                r["mean_room_utilization"]
            )
        )

    print("\n" + "="*60)
    print("BEST POLICY RECOMMENDATION")
    print("="*60)
    print("Recommended scheduling priority rule: " + str(best["priority_rule"]))
    print("Recommended holding bays: " + str(best["holding_bay"]["recommended_bays_p95"]))
    print("Recommended holding bay close time: " + str(best["holding_bay"]["recommended_close_p95"]))
    print("="*60 + "\n")

    return {
        "best": best,
        "ranked": ranked
    }

def buildCostInputsFromCaseTables():
    """
    Temporary helper using your case/exhibit values.
    Replace or extend later with automatically generated tables.
    """
    overcap_rows = [
        {"hb_count": 11, "days_with_instances": 196, "avg_instances_per_day": 14.42},
        {"hb_count": 12, "days_with_instances": 160, "avg_instances_per_day": 8.97},
        {"hb_count": 13, "days_with_instances": 126, "avg_instances_per_day": 5.40},
        {"hb_count": 14, "days_with_instances": 96,  "avg_instances_per_day": 3.02},
        {"hb_count": 15, "days_with_instances": 59,  "avg_instances_per_day": 1.49},
        {"hb_count": 16, "days_with_instances": 34,  "avg_instances_per_day": 0.78},
        {"hb_count": 17, "days_with_instances": 20,  "avg_instances_per_day": 0.34},
        {"hb_count": 18, "days_with_instances": 9,   "avg_instances_per_day": 0.12},
        {"hb_count": 19, "days_with_instances": 3,   "avg_instances_per_day": 0.05},
        {"hb_count": 20, "days_with_instances": 1,   "avg_instances_per_day": 0.00},
        {"hb_count": 21, "days_with_instances": 0,   "avg_instances_per_day": 0.00},
    ]

    empty_rows = [
        {"hb_count": 11, "avg_daily_empty_hour_blocks": 3.17},
        {"hb_count": 12, "avg_daily_empty_hour_blocks": 4.02},
        {"hb_count": 13, "avg_daily_empty_hour_blocks": 4.95},
        {"hb_count": 14, "avg_daily_empty_hour_blocks": 5.92},
        {"hb_count": 15, "avg_daily_empty_hour_blocks": 6.92},
        {"hb_count": 16, "avg_daily_empty_hour_blocks": 7.94},
        {"hb_count": 17, "avg_daily_empty_hour_blocks": 8.96},
        {"hb_count": 18, "avg_daily_empty_hour_blocks": 10.00},
        {"hb_count": 19, "avg_daily_empty_hour_blocks": 11.04},
        {"hb_count": 20, "avg_daily_empty_hour_blocks": 12.08},
        {"hb_count": 21, "avg_daily_empty_hour_blocks": 13.12},
    ]

    close_rows = [
        {"close_time": "17:30", "avg_occupancy": 6.05, "p95_occupancy": 11.56},
        {"close_time": "18:00", "avg_occupancy": 5.81, "p95_occupancy": 11.10},
        {"close_time": "18:30", "avg_occupancy": 4.66, "p95_occupancy": 9.38},
        {"close_time": "19:00", "avg_occupancy": 4.43, "p95_occupancy": 9.13},
        {"close_time": "19:30", "avg_occupancy": 3.42, "p95_occupancy": 7.73},
        {"close_time": "20:00", "avg_occupancy": 3.20, "p95_occupancy": 7.32},
        {"close_time": "20:30", "avg_occupancy": 2.40, "p95_occupancy": 5.93},
        {"close_time": "21:00", "avg_occupancy": 2.29, "p95_occupancy": 5.74},
        {"close_time": "21:30", "avg_occupancy": 1.88, "p95_occupancy": 5.09},
        {"close_time": "22:00", "avg_occupancy": 1.78, "p95_occupancy": 4.98},
        {"close_time": "22:30", "avg_occupancy": 1.43, "p95_occupancy": 4.11},
        {"close_time": "23:00", "avg_occupancy": 1.40, "p95_occupancy": 4.06},
        {"close_time": "23:30", "avg_occupancy": 1.16, "p95_occupancy": 3.66},
        {"close_time": "24:00", "avg_occupancy": 1.04, "p95_occupancy": 3.33},
    ]

    return overcap_rows, empty_rows, close_rows

def runCostAnalysis():
    """
    Run economic decision support using case-table inputs.
    """
    hb_params = HoldingBayCostParams()
    close_params = CloseTimeCostParams()

    overcap_rows, empty_rows, close_rows = buildCostInputsFromCaseTables()

    hb_results = summarize_hb_decision(
        overcap_rows,
        empty_rows,
        params=hb_params
    )

    close_results = summarize_close_time_decision(
        close_rows,
        params=close_params
    )

    return {
        "hb": hb_results,
        "close": close_results
    }

def printCostRecommendations(cost_results):
    hb_service = cost_results["hb"]["service_constraint_recommendation"]
    hb_cost = cost_results["hb"]["cost_recommendation"]
    close_cost = cost_results["close"]["cost_recommendation"]

    print("\n" + "="*60)
    print("*********COST-BASED DECISION SUPPORT*********")
    print("="*60)
    print("--- HOLDING BAY COST ANALYSIS ---")
    print("Holding bays meeting service constraint (<=10% days with overcapacity): " + str(int(hb_service["hb_count"])))
    print("Holding bays minimizing total holding-bay cost: " + str(int(hb_cost["hb_count"])))
    print("Minimum holding-bay total cost: $" + str(round(hb_cost["total_holding_bay_cost"], 2)))
    
    print("\n--- CLOSE TIME COST ANALYSIS ---")
    print("Best holding-bay close time by total cost: " + str(close_cost["close_time_hhmm"]))
    print("Estimated labor cost at best close time: $" + str(round(close_cost["estimated_labor_cost"], 2)))
    print("Estimated admission cost at best close time: $" + str(round(close_cost["admission_cost"], 2)))
    print("Estimated total cost at best close time: $" + str(round(close_cost["total_cost"], 2)))
    print("="*60 + "\n")


def renderVisualizationFigures(figs, showFigures=True, saveFigures=False, outDir="OutputData/Figures"):
    """
    Display and/or save matplotlib figures returned by VisualizationAnalysis.
    """
    if saveFigures and not os.path.exists(outDir):
        os.makedirs(outDir)

    for name, fig in figs.items():
        if saveFigures:
            fig.savefig(os.path.join(outDir, f"{name}.png"), dpi=200, bbox_inches="tight")
        if showFigures:
            display(fig)
        plt.close(fig)

def RunSimulation(
    myP,
    saveOutputs=True,
    printStats=True,
    printRecommendations=True,
    showVisualizations=False,
    saveVisualizations=False,
    policyResults=None,
    comparisonOptions=None,
    visualizationSourceNote="Source: EP/CATH simulation based on July 2015 case inputs; authors' analysis."
):

    ###### STEP 0: READ DATA / CREATE MODEL ######

    # read/process input data
    shifts = readShiftData(myP.shiftDataFile, myP.numShiftEntries)
    procedures = readProcData(myP.procDataFile, myP.numEntries)
    procedures = cleanProcTimes(procedures, myP.iProcTime, myP.turnover, myP.totalTimeRoom)

    # create time period model
    timePeriod = TimePeriod(myP)

    ###### STEP 1: SCHEDULE SHIFTS ######
    timePeriod.packShifts(shifts, myP)

    ###### STEP 2: PACK PROCEDURES INTO SHIFTS ######
    timePeriod.packProcedures(procedures, myP)

    ###### STEP 3: CALCULATE OUTPUT STATISTICS ######
    if printStats:
        avgUtilDay, avgUtilWeek = printOutputStatistics(timePeriod, procedures, myP)

    ###### STEP 4: SAVE RESULTS ######
    if saveOutputs:
        saveHoldingBayResults(timePeriod, myP.holdingBayWorkbook, myP)
        formatDataFileForVisualization(myP.resolution, myP.holdingBayWorkbook)
        ###### STEP 6: PRINT RECOMMENDATIONS ######
        printPlanningRecommendations(timePeriod, myP)
    
        ###### STEP 7: PRINT COST ANALYSIS ######
        printCostAnalysis(timePeriod, myP)
    
  
    ###### STEP 9: GENERATE VISUALIZATIONS (OPTIONAL) ######
    if hasattr(myP, 'generateVisualizations') and myP.generateVisualizations:
        try:
            import VisualizationAnalysis as VA
            import matplotlib.pyplot as plt
            import os
            
            # Build comprehensive summary
            from Simulation import buildScenarioSummary, buildCostInputsFromSimulation
            from CostAnalysis import (
                HoldingBayCostParams,
                CloseTimeCostParams,
                summarize_hb_decision,
                summarize_close_time_decision,
            )
            
            summary = buildScenarioSummary(timePeriod, procedures, myP, priorityName="historical")
            
            # Add cost analysis
            overcap_rows, empty_rows, close_rows = buildCostInputsFromSimulation(timePeriod, myP)
            hb_params = HoldingBayCostParams(simulated_days=timePeriod.numDays)
            close_params = CloseTimeCostParams()
            
            hb_results = summarize_hb_decision(overcap_rows, empty_rows, params=hb_params)
            close_results = summarize_close_time_decision(close_rows, params=close_params)
            
            summary["cost_analysis"] = {
                "hb": hb_results,
                "close": close_results
            }
            
            # Generate all visualizations
            print("\n" + "="*70)
            print("GENERATING VISUALIZATIONS...")
            print("="*70)
            
            figures = VA.build_all_key_figures(
                summary,
                policy_results=None,
                options=None,
                source_note="Source: EP/CATH simulation based on July 2015 data"
            )
            
            # Save figures
            output_dir = "OutputData/Figures"
            os.makedirs(output_dir, exist_ok=True)
            
            for name, fig in figures.items():
                filepath = os.path.join(output_dir, f"{name}.png")
                fig.savefig(filepath, dpi=300, bbox_inches='tight', facecolor='#F7F5F2')
                plt.close(fig)
            
            print(f"✓ Saved {len(figures)} visualizations to {output_dir}/")
            print("="*70 + "\n")
            
        except Exception as e:
            print(f"\nNote: Visualization generation skipped: {e}")
    ###### STEP 8: RETURN RESULTS ######
    return timePeriod, procedures
        

    ###### STEP 5: BUILD SUMMARY ######
    priorityName = "custom"
    try:
        if myP.sortIndex == myP.iHistoricalOrder:
            priorityName = "historical"
        elif myP.sortIndex == myP.iProcTime and myP.sortDescend:
            priorityName = "longest procedures first"
        elif myP.sortIndex == myP.iProcTime and not myP.sortDescend:
            priorityName = "shortest procedures first"
        elif myP.sortIndex == myP.iPostTime and myP.sortDescend:
            priorityName = "longest recovery time first"
        elif myP.sortIndex == myP.iPostTime and not myP.sortDescend:
            priorityName = "shortest recovery time first"
    except Exception:
        pass

    summary = buildScenarioSummary(timePeriod, procedures, myP, priorityName=priorityName)

    ###### STEP 6: RUN COST ANALYSIS ######
    try:
        cost_results = runCostAnalysis()
        summary["cost_analysis"] = cost_results
    except Exception as e:
        print(f"\nWarning: Cost analysis failed: {e}")
        cost_results = None

    ###### STEP 7: GENERATE VISUALIZATIONS ######
    figs = None
    if showVisualizations or saveVisualizations:
        try:
            figs = VA.build_all_key_figures(
                summary,
                policy_results=policyResults,
                options=comparisonOptions,
                source_note=visualizationSourceNote
            )
            summary["figure_names"] = list(figs.keys())

            renderVisualizationFigures(
                figs,
                showFigures=showVisualizations,
                saveFigures=saveVisualizations
            )
        except Exception as e:
            print(f"\nWarning: Visualization generation failed: {e}")

    ###### STEP 8: PRINT RECOMMENDATIONS ######
    if printRecommendations:
        printRecommendationReport(summary)
        if cost_results:
            printCostRecommendations(cost_results)

    return timePeriod, summary


import math

def percentile(values, pct):
    """Calculate percentile of a list of values."""
    if len(values) == 0:
        return 0
    vals = sorted(values)
    rank = int(math.ceil((pct / 100.0) * len(vals))) - 1
    rank = max(0, min(rank, len(vals) - 1))
    return vals[rank]

def hoursToClockTime(hoursFloat):
    """Convert hours from midnight to clock time (handles >24 hours)"""
    totalMinutes = int(round(hoursFloat * 60))
    days = totalMinutes // (24 * 60)
    remainingMinutes = totalMinutes % (24 * 60)
    hh = remainingMinutes // 60
    mm = remainingMinutes % 60
    
    if days > 0:
        return f"{hh}:{mm:02d} (+{days} day{'s' if days > 1 else ''})"
    else:
        return f"{hh}:{mm:02d}"

def printPlanningRecommendations(timePeriod, p):
    """Print planning recommendations based on simulation results."""
    
    holdingBays = timePeriod.bins[2]
    numSlots = int(p.HBCloseTime * (60.0 / p.resolution))
    
    dailyPeaks = []
    dailyLastOccupiedHours = []
    
    for d in range(timePeriod.numDays):
        occ = [holdingBays[(d, float(i))] for i in range(numSlots)]
        peak = max(occ) if len(occ) > 0 else 0
        dailyPeaks.append(peak)
        
        occupiedIdx = [i for i, x in enumerate(occ) if x > 0]
        if len(occupiedIdx) == 0:
            dailyLastOccupiedHours.append(0.0)
        else:
            lastIdx = occupiedIdx[-1]
            lastHour = (lastIdx * p.resolution) / 60.0
            dailyLastOccupiedHours.append(lastHour)
    
    overallPeak = max(dailyPeaks) if len(dailyPeaks) > 0 else 0
    peakP95 = percentile(dailyPeaks, 95)
    peakP90 = percentile(dailyPeaks, 90)
    lastOccP95 = percentile(dailyLastOccupiedHours, 95)
    lastOccP90 = percentile(dailyLastOccupiedHours, 90)
    overallLast = max(dailyLastOccupiedHours) if len(dailyLastOccupiedHours) > 0 else 0.0
    
    recommendedBays = int(math.ceil(peakP95))
    recommendedClose = hoursToClockTime(lastOccP95)
    
    cathUtil, epUtil, _, _, _ = timePeriod.getUtilizationStatistics(p)
    meanUtil = (cathUtil + epUtil) / 2.0
    
    print("\n" + "="*70)
    print("*********PLANNING RECOMMENDATIONS*********")
    print("="*70)
    
    print("\n--- HOLDING BAY RECOMMENDATIONS ---")
    print(f"Recommended holding bays (95th percentile daily peak): {recommendedBays} bays")
    print(f"Conservative (90th percentile): {int(math.ceil(peakP90))} bays")
    print(f"Worst-case peak observed: {overallPeak} bays")
    print(f"\nInterpretation: Build {recommendedBays} holding bay spaces to handle")
    print(f"95% of days without overcapacity.")
    
    print("\n--- HOLDING BAY OPERATING HOURS ---")
    print(f"Holding bays last occupied (95th percentile): {recommendedClose}")
    print(f"Conservative (90th percentile): {hoursToClockTime(lastOccP90)}")
    print(f"Worst-case last occupied: {hoursToClockTime(overallLast)}")
    print(f"\nInterpretation: Holding bays need to remain open past midnight.")
    print(f"On 95% of days, last patient leaves by {recommendedClose}.")
    
    print("\n--- LAB ROOM UTILIZATION ---")
    print(f"Cath lab average utilization: {round(cathUtil * 100, 2)}%")
    print(f"EP lab average utilization: {round(epUtil * 100, 2)}%")
    print(f"Overall average utilization: {round(meanUtil * 100, 2)}%")
    
    print("\n--- PROCEDURE SCHEDULING PERFORMANCE ---")
    print(f"Total procedures scheduled: {timePeriod.procsPlaced} / {timePeriod.numTotalProcs}")
    print(f"Procedures extending past room close time: {timePeriod.overflowCath + timePeriod.overflowEP}")
    print(f"  • Cath lab overflow: {timePeriod.overflowCath}")
    print(f"  • EP lab overflow: {timePeriod.overflowEP}")
    
    print("\n" + "="*70)
    print("KEY RECOMMENDATIONS:")
    print("="*70)
    print(f"1. BUILD: {recommendedBays} holding bay spaces")
    print(f"2. STAFF: Holding bays until {recommendedClose} (95% coverage)")
    print(f"3. UTILIZATION: Labs running at {round(meanUtil * 100, 1)}% capacity")
    print("="*70 + "\n")

def buildCostInputsFromSimulation(timePeriod, p):
    """Generate cost analysis input tables from simulation results."""
    holdingBays = timePeriod.bins[2]
    numSlots = int(p.HBCloseTime * (60.0 / p.resolution))
    
    overcap_rows = []
    empty_rows = []
    
    dailyPeaks = []
    for d in range(timePeriod.numDays):
        occ = [holdingBays[(d, float(i))] for i in range(numSlots)]
        dailyPeaks.append(max(occ) if len(occ) > 0 else 0)
    
    current_p95 = int(math.ceil(percentile(dailyPeaks, 95)))
    min_bays = max(current_p95 - 5, 1)
    max_bays = current_p95 + 6
    
    for bay_count in range(min_bays, max_bays):
        days_over = sum(1 for peak in dailyPeaks if peak > bay_count)
        total_instances = sum(max(0, peak - bay_count) for peak in dailyPeaks)
        avg_instances = total_instances / timePeriod.numDays
        pct_days = days_over / timePeriod.numDays
        
        overcap_rows.append({
            "hb_count": bay_count,
            "days_with_instances": days_over,
            "pct_days_with_instances": pct_days,
            "avg_instances_per_day": avg_instances
        })
        
        total_empty_hours = 0
        for d in range(timePeriod.numDays):
            occ = [holdingBays[(d, float(i))] for i in range(numSlots)]
            for occupancy in occ:
                empty = max(0, bay_count - occupancy)
                total_empty_hours += empty * (p.resolution / 60.0)
        
        avg_empty_hours = total_empty_hours / timePeriod.numDays
        
        empty_rows.append({
            "hb_count": bay_count,
            "avg_daily_empty_hour_blocks": avg_empty_hours
        })
    
    close_rows = []
    for close_hour in range(17, 25):
        close_slot = int(close_hour * (60.0 / p.resolution))
        
        occupancy_after = []
        for d in range(timePeriod.numDays):
            occ = [holdingBays[(d, float(i))] for i in range(numSlots)]
            if close_slot < len(occ):
                after = occ[close_slot:]
                avg_after = sum(after) / len(after) if after else 0
                occupancy_after.append(avg_after)
        
        avg_occ = sum(occupancy_after) / len(occupancy_after) if occupancy_after else 0
        p95_occ = percentile(occupancy_after, 95) if occupancy_after else 0
        
        close_rows.append({
            "close_time": f"{close_hour % 24}:00",
            "avg_occupancy": avg_occ,
            "p95_occupancy": p95_occ
        })
    
    return overcap_rows, empty_rows, close_rows

def printCostAnalysis(timePeriod, p):
    """Run and print cost-based decision analysis."""
    try:
        from CostAnalysis import (
            HoldingBayCostParams,
            CloseTimeCostParams,
            summarize_hb_decision,
            summarize_close_time_decision,
        )
        
        overcap_rows, empty_rows, close_rows = buildCostInputsFromSimulation(timePeriod, p)
        
        hb_params = HoldingBayCostParams(simulated_days=timePeriod.numDays)
        close_params = CloseTimeCostParams()
        
        hb_results = summarize_hb_decision(overcap_rows, empty_rows, params=hb_params)
        close_results = summarize_close_time_decision(close_rows, params=close_params)
        
        print("\n" + "="*70)
        print("*********COST-BASED DECISION SUPPORT*********")
        print("="*70)
        
        print("\n--- HOLDING BAY CAPACITY ANALYSIS ---")
        service_rec = hb_results["service_constraint_recommendation"]
        cost_rec = hb_results["cost_recommendation"]
        
        print(f"Service-constrained recommendation: {int(service_rec['hb_count'])} bays")
        print(f"  (Meets ≤5% days with overcapacity constraint)")
        print(f"  Total daily cost: ${service_rec['total_holding_bay_cost']:.2f}")
        
        print(f"\nCost-minimizing recommendation: {int(cost_rec['hb_count'])} bays")
        print(f"  Total daily cost: ${cost_rec['total_holding_bay_cost']:.2f}")
        print(f"  Days with overcapacity: {int(cost_rec['days_with_instances'])} ({cost_rec['pct_days_with_instances']*100:.1f}%)")
        
        print("\nCost breakdown (cost-minimizing option):")
        print(f"  • Cancellation costs: ${cost_rec['cancellation_cost']:.2f}/day")
        print(f"  • Empty bay costs: ${cost_rec['empty_holding_bay_cost']:.2f}/day")
        
        print("\n--- HOLDING BAY OPERATING HOURS ANALYSIS ---")
        close_rec = close_results["cost_recommendation"]
        
        print(f"Cost-minimizing close time: {close_rec['close_time_hhmm']}")
        print(f"  Incremental hours beyond 17:00: {close_rec['incremental_hours']:.1f} hours/day")
        print(f"  Total incremental cost: ${close_rec['total_cost']:.2f}/day")
        
        print("\nCost breakdown:")
        print(f"  • Labor cost (base + overtime): ${close_rec['estimated_labor_cost']:.2f}/day")
        print(f"  • Admission cost: ${close_rec['admission_cost']:.2f}/day")
        print(f"  • Patients admitted at close (95th percentile): {close_rec['admitted_patients_95']:.1f}")
        
        print("\n" + "="*70)
        print("RECOMMENDED DECISION:")
        print("="*70)
        
        if service_rec['hb_count'] == cost_rec['hb_count']:
            print(f"Build {int(cost_rec['hb_count'])} holding bays")
            print("  (Both service and cost objectives align)")
        else:
            print(f"Build {int(service_rec['hb_count'])} holding bays")
            cost_diff = service_rec['total_holding_bay_cost'] - cost_rec['total_holding_bay_cost']
            print(f"  (Service constraint prioritized; costs ${cost_diff:.2f}/day more than minimum)")
        
        print(f"\nOperate holding bays until {close_rec['close_time_hhmm']}")
        print(f"  (Minimizes total cost of labor + admissions)")
        print("="*70 + "\n")
        
    except ImportError as e:
        print("\nNote: Cost analysis module not available.")
        print(f"Error: {e}")
    except Exception as e:
        print(f"\nWarning: Cost analysis failed: {e}")
        import traceback
        traceback.print_exc()
        
def Start():
    """
    Main entry point - sets up parameters using widgets and runs simulation.
    """
    print("Starting simulation...")

    # create Params instance
    p = Params()

    # set random seed for reproducibility
    random.seed(30)

    # call Widgets to set Params using GUI
    p.setParams()
    
    print("\nParameters set. Ready to run simulation.")
    print("Call RunSimulation(p) to execute, or comparePriorityRules(p) to compare policies.")
    
    return p

# For non-interactive use in Colab
def RunWithDefaults(priorityRule='historical', saveOutputs=True, printStats=True, 
                    printRecommendations=True, showVisualizations=False):
    """
    Run simulation with default parameters without widget interaction.
    Useful for Google Colab when widgets don't work properly.
    
    Args:
        priorityRule: One of PRIORITY_OPTIONS
        saveOutputs: Whether to save CSV outputs
        printStats: Whether to print detailed statistics
        printRecommendations: Whether to print recommendation report
        showVisualizations: Whether to display visualizations
    """
    print("Running simulation with default parameters...")
    
    # Create Params and set defaults programmatically
    p = Params()
    
    # Set random seed
    random.seed(30)
    
    # Apply priority rule
    applyPriorityRule(p, priorityRule)
    
    # Run simulation
    timePeriod, summary = RunSimulation(
        p,
        saveOutputs=saveOutputs,
        printStats=printStats,
        printRecommendations=printRecommendations,
        showVisualizations=showVisualizations
    )
    
    return timePeriod, summary, p


# Example usage for Colab:
if __name__ == "__main__":
    print("\n" + "="*60)
    print("EP/CATH LAB SIMULATION")
    print("="*60)
    print("\nUsage:")
    print("  1. With widgets (interactive): p = Start()")
    print("  2. Without widgets (programmatic): timePeriod, summary, p = RunWithDefaults()")
    print("  3. Compare policies: results = comparePriorityRules(p)")
    print("\n" + "="*60 + "\n")
