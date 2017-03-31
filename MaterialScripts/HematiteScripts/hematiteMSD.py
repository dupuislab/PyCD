#!/usr/bin/env python

def hematiteMSD(trajectoryDataFileName, shellCharges, cutE, dirPath, nStepsMSD, nDispMSD, binsize, reprTime, reprDist, 
                outdir):

    from KineticModel import analysis
    import numpy as np
    import pickle
    import platform
    
    materialName = 'hematite'
    tailName = '_Shell' if shellCharges else '_NoShell' + '_E' + str(cutE) + '.obj'
    directorySeparator = '\\' if platform.uname()[0]=='Windows' else '/'
    objectFileDirectoryName = 'ObjectFiles'
    objectFileDirPath = dirPath + directorySeparator + objectFileDirectoryName
    materialFileName = objectFileDirPath + directorySeparator + materialName + tailName
    
    file_hematite = open(materialFileName, 'r')
    hematite = pickle.load(file_hematite)
    file_hematite.close()
    
    trajectoryData = np.load(trajectoryDataFileName)
    hematiteAnalysis = analysis(hematite, trajectoryData[()], nStepsMSD, nDispMSD, binsize, 
                                reprTime, reprDist)
    
    timeArray = trajectoryData[()].timeArray
    unwrappedPositionArray = trajectoryData[()].unwrappedPositionArray
    msdAnalysisData = hematiteAnalysis.computeMSD(timeArray, unwrappedPositionArray, outdir, report=1)
    msdData = msdAnalysisData.msdData
    speciesTypes = msdAnalysisData.speciesTypes
    fileName = msdAnalysisData.fileName
    hematiteAnalysis.displayMSDPlot(msdData, speciesTypes, fileName, outdir)