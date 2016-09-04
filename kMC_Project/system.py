#!/usr/bin/env python
'''
code to compute msd of random walk of single electron in 3D hematite lattice structure
 switch off PBC, and 
'''
import numpy as np
import random as rnd

class modelParameters(object):
    '''
    Definitions of all model parameters that need to be passed on to other classes
    '''
    def __init__(self, T, ntraj, kmcsteps, stepInterval, nsteps_msd, ndisp_msd, binsize, 
                 systemSize=np.array([10, 10, 10]), pbc=1, gui=0, kB=8.617E-05):
        '''
        Definitions of all model parameters
        '''
        # TODO: Is it necessary/better to define these parameters in a dictionary?
        self.T = T
        self.ntraj = ntraj
        self.kmcsteps = kmcsteps
        self.stepInterval = stepInterval
        self.nsteps_msd = nsteps_msd
        self.ndisp_msd = ndisp_msd
        self.binsize = binsize
        self.systemSize = systemSize
        self.pbc = pbc
        self.gui = gui
        self.kB = kB
        
class material(object):
    '''
    defines the structure of working material
    
    Attributes:
        name: A string representing the material name
        elements: list of element symbols
        species_to_sites: dictionary that maps species to sites
        pos: positions of elements in the unit cell
        index: element index of the positions starting from 0
        charge: atomic charges of the elements # first shell atomic charges to be included
        latticeParameters: list of three lattice constants in angstrom and three angles between them in degrees
        # TODO: lattice constants and unit cell matrix may be defined in here
    '''
    
    def __init__(self, name, elementTypes, speciesTypes, unitcellCoords, elementTypeIndexList, chargeTypes, 
                 latticeParameters, vn, lambdaValues, VAB, neighborCutoffDist, neighborCutoffDistTol):
        '''
        Return an material object whose name is *name* 
        '''
        # TODO: introduce a method to view the material using ase atoms or other gui module
        self.name = name
        self.elementTypes = elementTypes
        self.speciesTypes = speciesTypes
        for key in speciesTypes:
            assert set(speciesTypes[key]) <= set(elementTypes), 'Specified sites should be a subset of elements'
        self.unitcellCoords = unitcellCoords
        startIndex = 0
        for elementIndex in range(len(elementTypes)):
            elementUnitCellCoords = unitcellCoords[elementTypeIndexList==elementIndex]
            endIndex = startIndex + len(elementUnitCellCoords)
            self.unitcellCoords[startIndex:endIndex] = elementUnitCellCoords[elementUnitCellCoords[:,2].argsort()]
            startIndex = endIndex
        self.elementTypeIndexList = elementTypeIndexList.astype(int)
        self.chargeTypes = chargeTypes
        self.latticeParameters = latticeParameters
        self.vn = vn
        self.lambdaValues = lambdaValues
        self.VAB = VAB
        self.neighborCutoffDist = neighborCutoffDist
        self.neighborCutoffDistTol = neighborCutoffDistTol
        
        # number of elements
        length = len(self.elementTypes)
        nElements = np.zeros(length, int)
        for elementIndex in range(length):
            nElements[elementIndex] = np.count_nonzero(self.elementTypeIndexList == elementIndex)
        self.nElements = nElements
        
        # siteList
        siteList = []
        for key in self.speciesTypes:
            if key != 'empty':
                siteList.extend(self.speciesTypes[key])
        siteList = list(set(siteList))
        self.siteList = siteList
        
        # number of sites present in sitelist
        nSites = np.zeros(len(self.siteList), int)
        for elementTypeIndex, elementType in enumerate(self.elementTypes):
            if elementType in siteList:
                nSites[elementTypeIndex] = len(np.where(self.elementTypeIndexList == elementTypeIndex)[0])
        self.nSites = nSites

        # lattice cell matrix
        [a, b, c, alpha, beta, gamma] = self.latticeParameters
        cell = np.array([[ a                , 0                , 0],
                         [ b * np.cos(gamma), b * np.sin(gamma), 0],
                         [ c * np.cos(alpha), c * np.cos(beta) , c * np.sqrt(np.sin(alpha)**2 - np.cos(beta)**2)]]) # cell matrix
        self.latticeMatrix = cell

    def generateSites(self, elementTypeIndices, cellSize=np.array([1, 1, 1])):
        '''
        Returns systemElementIndices and coordinates of specified elements in a cell of size *cellSize*
        '''
        assert all(size > 0 for size in cellSize), 'Input size should always be greater than 0'
        extractIndices = np.in1d(self.elementTypeIndexList, elementTypeIndices).nonzero()[0]
        unitcellElementCoords = self.unitcellCoords[extractIndices]
        numCells = np.prod(cellSize)
        nSites = len(unitcellElementCoords)
        unitcellElementIndexList = np.arange(nSites)
        unitcellElementTypeIndex = np.reshape(np.concatenate((np.asarray([[elementTypeIndex] * self.nElements[elementTypeIndex] 
                                                                          for elementTypeIndex in elementTypeIndices]))), (nSites, 1))
        unitCellElementTypeElementIndexList = np.reshape(np.concatenate(([np.arange(self.nElements[elementTypeIndex]) 
                                                                          for elementTypeIndex in elementTypeIndices])), (nSites, 1))
        cellCoordinates = np.zeros((numCells * nSites, 3))
        # quantumIndex = [unitCellIndex, elementTypeIndex, elementIndex]
        quantumIndexList = np.zeros((numCells * nSites, 5), dtype=int)
        systemElementIndexList = np.zeros(numCells * nSites, dtype=int)
        iUnitCell = 0
        for xSize in range(cellSize[0]):
            for ySize in range(cellSize[1]):
                for zSize in range(cellSize[2]): 
                    startIndex = iUnitCell * nSites
                    endIndex = startIndex + nSites
                    newCellSiteCoords = unitcellElementCoords + np.dot([xSize, ySize, zSize], self.latticeMatrix)
                    cellCoordinates[startIndex:endIndex, :] = newCellSiteCoords 
                    systemElementIndexList[startIndex:endIndex] = iUnitCell * nSites + unitcellElementIndexList
                    quantumIndexList[startIndex:endIndex] = np.hstack((np.tile(np.array([xSize, ySize, zSize]), (nSites, 1)), unitcellElementTypeIndex, unitCellElementTypeElementIndexList))
                    iUnitCell += 1

        returnSites = returnValues()
        returnSites.cellCoordinates = cellCoordinates
        returnSites.quantumIndexList = quantumIndexList
        returnSites.systemElementIndexList = systemElementIndexList
        return returnSites
    
    def generateSystemElementIndex(self, systemSize, quantumIndex):
        '''
        Returns the systemElementIndex of the element
        '''
        unitCellIndex = quantumIndex[:3]
        [elementTypeIndex, elementIndex] = quantumIndex[-2:]
        nElementsPerUnitCell = np.sum(self.nElements)
        systemElementIndex = (elementIndex + np.sum(self.nElements[:elementTypeIndex]) + nElementsPerUnitCell * 
                              (unitCellIndex[2] + unitCellIndex[1] * systemSize[2] + unitCellIndex[0] * 
                               np.prod(systemSize[1:])))
        return systemElementIndex
    
class system(object):
    '''
    defines the system we are working on
    
    Attributes:
    size: An array (3 x 1) defining the system size in multiple of unit cells
    '''
    
    def __init__(self, modelParameters, material, occupancy, elementTypeDelimiter):
        '''
        Return a system object whose size is *size*
        '''
        self.modelParameters = modelParameters
        self.material = material
        self.occupancy = occupancy
        self.elementTypeDelimiter = elementTypeDelimiter
        
        # total number of unit cells
        self.numCells = np.prod(self.modelParameters.systemSize)
        
        # generate all sites in the system
        elementTypeIndices = range(len(self.material.elementTypes))
        bulkSites = self.material.generateSites(elementTypeIndices, self.modelParameters.systemSize)
        self.bulkSites = bulkSites
        
        # generate lattice charge list
        unitCellChargeList = np.array([self.material.chargeTypes[self.material.elementTypes[elementTypeIndex]] 
                                       for elementTypeIndex in self.material.elementTypeIndexList])
        self.latticeChargeList = np.tile(unitCellChargeList, self.numCells)
    
    # TODO: Is it better to shift neighborSites method to material class and add generateNeighborList method to 
    # __init__ function of system class?   
    def neighborSites(self, bulkSites, centerSiteIndices, neighborSiteIndices, cutoffDistLimits):
        '''
        Returns systemElementIndexMap and distances between center sites and its neighbor sites within cutoff 
        distance
        '''
        neighborSiteCoords = bulkSites.cellCoordinates[neighborSiteIndices]
        neighborSiteSystemElementIndexList = bulkSites.systemElementIndexList[neighborSiteIndices]
        neighborSiteQuantumIndexList = bulkSites.quantumIndexList[neighborSiteIndices]
        centerSiteCoords = bulkSites.cellCoordinates[centerSiteIndices]
        centerSiteSystemElementIndexList = bulkSites.systemElementIndexList[centerSiteIndices]
        centerSiteQuantumIndexList = bulkSites.quantumIndexList[centerSiteIndices]
        
        neighborSystemElementIndices = []
        offsetList = [] 
        neighborElementIndexList = []
        numNeighbors = []
        displacementVectorList = []
        displacementList = []
        for centerSiteIndex, centerCoord in enumerate(centerSiteCoords):
            iDisplacementVectors = []
            iDisplacements = []
            iNeighborSiteIndexList = []
            for neighborSiteIndex, neighborCoord in enumerate(neighborSiteCoords):
                displacementVector = neighborCoord - centerCoord
                if not self.modelParameters.pbc:
                    displacement = np.linalg.norm(displacementVector)
                else:
                    # TODO: Use minimum image convention to compute the distance
                    displacement = np.linalg.norm(displacementVector)
                if cutoffDistLimits[0] < displacement <= cutoffDistLimits[1]:
                    iNeighborSiteIndexList.append(neighborSiteIndex)
                    iDisplacementVectors.append(displacementVector)
                    iDisplacements.append(displacement)
            neighborSystemElementIndices.append(np.array(neighborSiteSystemElementIndexList[iNeighborSiteIndexList]))
            offsetList.append(centerSiteQuantumIndexList[centerSiteIndex, :3] - neighborSiteQuantumIndexList[iNeighborSiteIndexList, :3])
            neighborElementIndexList.append(neighborSiteQuantumIndexList[iNeighborSiteIndexList, 4])
            numNeighbors.append(len(iNeighborSiteIndexList))
            displacementVectorList.append(np.asarray(iDisplacementVectors))
            displacementList.append(iDisplacements)
        # TODO: Avoid conversion and initialize the object beforehand
        neighborSystemElementIndices = np.asarray(neighborSystemElementIndices)
        systemElementIndexMap = np.empty(2, dtype=object)
        systemElementIndexMap[:] = [centerSiteSystemElementIndexList, neighborSystemElementIndices]
        offsetList = np.asarray(offsetList)
        neighborElementIndexList = np.asarray(neighborElementIndexList)
        elementIndexMap = np.empty(2, dtype=object)
        elementIndexMap[:] = [centerSiteQuantumIndexList[:,4], neighborElementIndexList]
        numNeighbors = np.asarray(numNeighbors, int)
        
        returnNeighbors = returnValues()
        returnNeighbors.systemElementIndexMap = systemElementIndexMap
        returnNeighbors.offsetList = offsetList
        returnNeighbors.elementIndexMap = elementIndexMap
        returnNeighbors.numNeighbors = numNeighbors
        # TODO: Avoid conversion and initialize the object beforehand
        returnNeighbors.displacementVectorList = np.asarray(displacementVectorList)
        returnNeighbors.displacementList = np.asarray(displacementList)
        return returnNeighbors

    def generateNeighborList(self):
        '''
        Adds the neighbor list to the system object and returns the neighbor list
        '''
        neighborList = {}
        tolDist = self.material.neighborCutoffDistTol
        elementTypes = self.material.elementTypes
        systemSize = self.modelParameters.systemSize
        for cutoffDistKey in self.material.neighborCutoffDist.keys():
            cutoffDistList = self.material.neighborCutoffDist[cutoffDistKey]
            neighborListCutoffDistKey = []
            if cutoffDistKey is not 'E':
                [centerElementType, neighborElementType] = cutoffDistKey.split(self.elementTypeDelimiter)
                centerSiteElementTypeIndex = elementTypes.index(centerElementType) 
                neighborSiteElementTypeIndex = elementTypes.index(neighborElementType)
                centerSiteIndices = [self.material.generateSystemElementIndex(systemSize, np.array([1, 1, 1, centerSiteElementTypeIndex, elementIndex])) 
                                     for elementIndex in range(self.material.nElements[centerSiteElementTypeIndex])]
                neighborSiteIndices = [self.material.generateSystemElementIndex(systemSize, np.array([xSize, ySize, zSize, neighborSiteElementTypeIndex, elementIndex])) 
                                       for xSize in range(systemSize[0]) for ySize in range(systemSize[1]) 
                                       for zSize in range(systemSize[2]) 
                                       for elementIndex in range(self.material.nElements[neighborSiteElementTypeIndex])]
                for cutoffDist in cutoffDistList:
                    cutoffDistLimits = [cutoffDist-tolDist, cutoffDist+tolDist]
                    # TODO: include assertions, conditions for systemSizes less than [3, 3, 3]
                    neighborListCutoffDistKey.append(self.neighborSites(self.bulkSites, centerSiteIndices, 
                                                                        neighborSiteIndices, cutoffDistLimits))                    
            else:
                centerSiteIndices = neighborSiteIndices = np.arange(self.numCells * np.sum(self.material.nElements))
                cutoffDistLimits = [0, cutoffDistList[0]]
                neighborListCutoffDistKey.append(self.neighborSites(self.bulkSites, centerSiteIndices, 
                                                                    neighborSiteIndices, cutoffDistLimits))
            neighborList[cutoffDistKey] = neighborListCutoffDistKey
        self.neighborList = neighborList
        return neighborList

    def chargeConfig(self, occupancy):
        '''
        Returns charge distribution of the current configuration
        '''
        chargeList = self.latticeChargeList
        chargeTypes = self.material.chargeTypes
        chargeTypeKeys = chargeTypes.keys()
        shellChargeTypeKeys = [key for key in chargeTypeKeys if key not in self.material.siteList]
        for chargeTypeKey in shellChargeTypeKeys:
            centerElementType = chargeTypeKey.split(self.elementTypeDelimiter)[0]
            neighborElementTypeSites = self.neighborList[chargeTypeKey]
            for shellIndex, chargeValue in enumerate(chargeTypes[chargeTypeKey]):
                chargeTypeKeySystemElementIndexMap = neighborElementTypeSites[shellIndex].systemElementIndexMap
                extractIndices = np.in1d(chargeTypeKeySystemElementIndexMap[0], occupancy[centerElementType]).nonzero()[0]
                chargeTypeKeySystemElementIndices = np.unique(np.concatenate((chargeTypeKeySystemElementIndexMap[1][extractIndices])))
                chargeList[chargeTypeKeySystemElementIndices] = chargeValue
        return chargeList

    def config(self, occupancy):
        '''
        Generates the configuration array for the system 
        '''
        elementTypeIndices = range(len(self.material.elementTypes))
        systemSites = self.material.generateSites(elementTypeIndices, self.modelParameters.systemSize)
        positions = systemSites.cellCoordinates
        systemElementIndexList = systemSites.systemElementIndexList
        chargeList = self.chargeConfig(occupancy)
        
        returnConfig = returnValues()
        returnConfig.positions = positions
        returnConfig.chargeList = chargeList
        returnConfig.systemElementIndexList = systemElementIndexList
        returnConfig.occupancy = occupancy
        return returnConfig

class run(object):
    '''
    defines the subroutines for running Kinetic Monte Carlo and computing electrostatic interaction energies 
    '''
    def __init__(self, modelParameters, material, system):
        '''
        Returns the PBC condition of the system
        '''
        self.modelParameters = modelParameters
        self.material = material
        self.system = system

    def elec(self, occupancy, charge):
        '''
        Subroutine to compute the electrostatic interaction energies
        '''
        elec = 0
        return elec
        
    def delG0(self, occupancy, charge):
        '''
        Subroutine to compute the difference in free energies between initial and final states of the system
        '''
        delG0 = self.elec(occupancy, charge)
        return delG0
    
    def do_kmc_steps(self, occupancy, charge, stepInterval, kmcsteps):
        '''
        Subroutine to run the kmc simulation by specified number of steps
        '''
        T = self.modelParameters.T
        kB = self.modelParameters.kB
        vn = self.material.vn
        lambda_basal = self.material.lambda_basal
        lambda_c_direction = self.material.lambda_c_direction
        VAB_basal = self.material.VAB_basal
        VAB_c_direction = self.material.VAB_c_direction
        N_basal = self.material.N_basal
        N_c_direction = self.material.N_c_direction

        siteList = []
        for key in self.material.species_to_sites:
            if key != 'empty':
                siteList.extend(self.material.species_to_sites[key])
        siteList = list(set(siteList))
        siteIndexList = []
        for site in siteList:
            if site in self.material.elementTypes:
                siteIndexList.append(self.material.elementTypes.index(site))

        displacementMatrix = [material.displacementList(self.material, siteIndex) for siteIndex in siteIndexList] 
        delG0 = self.delG0(occupancy, charge)
        delGs_basal = ((lambda_basal + delG0)**2 / (4 * lambda_basal)) - VAB_basal
        delGs_c_direction = ((lambda_c_direction + delG0)**2 / (4 * lambda_c_direction)) - VAB_c_direction        
        k_basal = vn * np.exp(-delGs_basal / (kB * T))
        k_c_direction = vn * np.exp(-delGs_c_direction / (kB * T))
        nsteps_path = kmcsteps / stepInterval
        N_procs = N_basal + N_c_direction
        k_total = N_basal * k_basal + N_c_direction * k_c_direction
        k = np.array([k_basal, k_basal, k_basal, k_c_direction])
        k_cumsum = np.cumsum(k / k_total)
        
        # TODO: timeNdisplacement, not timeNpath
        timeNpath = np.zeros((nsteps_path+1, 4))
        # TODO: change the logic for layer selection which is specific to the hematite system
        layer = 0 if rnd.random() < 0.5 else 4
        time = 0
        displacement = 0
        for step in range(1, kmcsteps+1):
                rand = rnd.random()
                for i in range(N_procs):
                        if rand <= k_cumsum[i]:
                            # TODO: siteIndex
                            displacement += displacementMatrix[siteIndex].displacementList[layer + i]
                            time -= np.log(rnd.random()) / k_total
                            break
                if step % stepInterval == 0:
                        path_step = step / stepInterval
                        timeNpath[path_step, 0] = timeNpath[path_step-1, 0] + time
                        timeNpath[path_step, 1:] = timeNpath[path_step-1, 1:] + displacement
                        displacement = 0
                        time = 0
                layer = 0 if layer==4 else 4

class analysis(object):
    '''
    Post-simulation analysis methods
    '''
    
    def __init__(self):
        '''
        
        '''
        
    def compute_sd(self, timeNdisplacement):
        '''
        Subroutine to compute the squared displacement of the trajectories
        '''
        # timeNdisplacement, not timeNpath
        nsteps_msd = modelParameters.nsteps_msd
        ndisp_msd = modelParameters.ndisp_msd
        sec_to_ns = 1E+09
        time = timeNdisplacement[:, 0] * sec_to_ns
        path = timeNdisplacement[:, 1:]
        sd_array = np.zeros((nsteps_msd * ndisp_msd, 2))
        for timestep in range(1, nsteps_msd+1):
                sum_sd_timestep = 0
                for step in range(ndisp_msd):
                        sd_timestep = sum((path[step + timestep] - path[step])**2)
                        sd_array[(timestep-1) * ndisp_msd + step, 0] = time[step + timestep] - time[step]
                        sd_array[(timestep-1) * ndisp_msd + step, 1] = sd_timestep
                        sum_sd_timestep += sd_timestep
        return sd_array
    
    def compute_msd(self, sd_array):
        '''
        subroutine to compute the mean squared displacement
        '''
        nsteps_msd = modelParameters.nsteps_msd
        ndisp_msd = modelParameters.ndisp_msd
        binsize = modelParameters.binsize
        sd_array =  sd_array[sd_array[:, 0].argsort()] # sort sd_traj array by time column
        sd_array[:,0] = np.floor(sd_array[:,0])
        time_final = np.ceil(sd_array[nsteps_msd * ndisp_msd - 1, 0])
        nbins = int(np.ceil(time_final / binsize)) + 1
        time_array = np.arange(0, time_final+1, binsize) + 0.5 * binsize

        msd_array = np.zeros((nbins, 2))
        msd_array[:,0] = time_array
        for ibin in range(nbins):
                msd_array[ibin, 1] = np.mean(sd_array[sd_array[:,0] == ibin, 1])
        return msd_array

    
class plot(object):
    '''
    
    '''
    
    def __init__(self):
        '''
        
        '''
    
    def plot(self, msd):
        '''
        
        '''
        import matplotlib.pyplot as plt
        plt.figure(1)
        plt.plot(msd[:,0], msd[:,1])
        plt.xlabel('Time (ns)')
        plt.ylabel('MSD (Angstrom**2)')
        #plt.show()
        #plt.savefig(figname)

class returnValues(object):
    '''
    Returns the values of displacement list and respective coordinates in an object
    '''
    pass
