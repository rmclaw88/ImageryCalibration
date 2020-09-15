import os
import math
import arcpy    # Arcpy 3.8 (Arcpy Pro)
import pathlib
import shutil
from itertools import chain

"""To Use, Create a folder Named 'Uncompress' and DUMP All your landsat Scene folder within it
The Uncompress folder should be in the same root directory as this python file
For Only Landsat TM, ETM+ and OLI (5,7 and 8 Respectively)
Used to Perform Radiometric Calibration, Atmospheric Correction and Composite on VIS-IR Bands"""

sunElev = 0
GainsOffset = {}


def removeGapMaskDir():
    rootDir = pathlib.Path(os.path.join(os.path.dirname(__file__), 'Uncompress'))
    for root, folders, files in os.walk(rootDir):
        for folder in folders:
            if folder.startswith('gap_mask'):
                gapMaskDir = os.path.join(root, folder)
                shutil.rmtree(gapMaskDir)
                print(gapMaskDir, " Deleted")
    landsatPreProcess(rootDir)


def landsatPreProcess(workingDir):
    ResultsFolder = pathlib.Path(os.path.join(os.path.dirname(__file__), "Processed"))
    os.makedirs(ResultsFolder, exist_ok=True)
    print("\n\nResults Folder Created\n")
    for root, folders, files in os.walk(workingDir):
        for folder in folders:
            SceneDir = os.path.join(root, folder)
            try:
                print(SceneDir)
                arcpy.env.workspace = SceneDir
                arcpy.env.overwriteOutput = True
                Scene = ((os.path.split(SceneDir))[-1])
                RefSceneFolder = Scene + "_Preprocessed"
                RefSavePath = os.path.join(ResultsFolder, "SurfaceReflectance",  RefSceneFolder)
                os.makedirs(RefSavePath, exist_ok=True)
                print("Surface Reflectance Directory for Bands Created")
                arcpy.CheckOutExtension("spatial")
                readSunElevation(SceneDir)
                print("Retrieved Sun Elevation for Scene is {0}\n".format(sunElev))
                radiance_cor = math.sin(math.radians(sunElev))
                if Scene.startswith("LC08"):
                    l8_bands = arcpy.ListRasters(raster_type="TIF")
                    VisNir_bands = l8_bands[3:9]
                    for band8 in VisNir_bands:
                        print(band8)
                        Correction(SceneDir, band8, radiance_cor, RefSavePath)
                elif Scene.startswith("LE07"):
                    l7 = arcpy.ListRasters(raster_type="TIF")
                    visIR7 = list(chain(l7[0:5], [l7[7]]))
                    for band7 in visIR7:
                        print(band7)
                        Correction(SceneDir, band7, radiance_cor, RefSavePath)
                elif Scene.startswith("LT05") or Scene.startswith("LT04"):
                    l54 = arcpy.ListRasters(raster_type="TIF")
                    visIR54 = list(chain(l54[0:5], [l54[6]]))
                    for band54 in visIR54:
                        print(band54)
                        Correction(SceneDir, band54, radiance_cor, RefSavePath)
                elif Scene.startswith("LM04") or Scene.startswith("LM04"):
                    l45 = arcpy.ListRasters(raster_type="TIF")
                    visIR45 = l45[0:4]
                    for band45 in visIR45:
                        print(band45)
                        Correction(SceneDir, band45, radiance_cor, RefSavePath)
                else:
                    print(Scene, " May Not Be a Valid Landsat Scene Folder")
            except WindowsError:
                print("Folder Already Exists")
    landsatComposite(ResultsFolder)


def readSunElevation(CurWorkspace):
    global sunElev
    for root, directory, files in os.walk(CurWorkspace):
        for file in files:
            if file.endswith("MTL.txt"):
                metadata = os.path.join(root, file)
                with open(metadata, "r") as MTL:
                    for line in MTL:
                        if line.__contains__("SUN_ELEVATION"):
                            sunElev = float(line.strip().split("=")[1])
                            return sunElev
                MTL.close()


def readGainsOffset(curWorkspace, bandValue):
    global GainsOffset
    for root, directory, files in os.walk(curWorkspace):
        for file in files:
            if file.endswith("MTL.txt"):
                metadata = os.path.join(root, file)
                with open(metadata, "r") as MTL:
                    for line in MTL:
                        if line.__contains__("REFLECTANCE_MULT_BAND_" + bandValue) or \
                                line.__contains__("REFLECTANCE_ADD_BAND_" + bandValue):
                            row = line.strip().split("=")
                            GainsOffset[row[0].strip()] = float(row[1])
                MTL.close()


def Correction(env, band, radiance, saveDir):
    arcpy.CheckOutExtension('Spatial')
    specificBand = str(band.split("_")[-1][1])
    readGainsOffset(env, specificBand)
    band_RefMul = GainsOffset['REFLECTANCE_MULT_BAND_' + specificBand]
    band_RefAdd = GainsOffset['REFLECTANCE_ADD_BAND_' + specificBand]
    print("{0} has a Gain, Offset and Radiance Values of {1}, {2} and {3} Respectively".
          format(band, band_RefMul, band_RefAdd, radiance))
    print("Setting NoData Value and Executing Radiometric Calibration...")
    ret_name = band.split("_")
    bandName = "Scene_" + ret_name[2] + "_" + ret_name[3] + "_" + ret_name[7].strip(".TIF") + "_SurRef.tif"
    arcpy.SetRasterProperties_management(band, nodata="1 0")
    bandNom_P1 = arcpy.sa.Times(band, band_RefMul)
    bandNom_P2 = arcpy.sa.Plus(bandNom_P1, band_RefAdd)
    bandCor = arcpy.sa.Divide(bandNom_P2, radiance)
    bandCor_min = arcpy.GetRasterProperties_management(in_raster=bandCor, property_type="MINIMUM")
    bandCor_minVal = float(bandCor_min.getOutput(0))
    band_refCor = arcpy.sa.Minus(bandCor, bandCor_minVal)
    print("Saving Surface Reflectance Output...")
    OutRefName = (os.path.join(saveDir, bandName))
    band_refCor.save(OutRefName)
    print("Saved Radiometric Calibration for " + band + "\n")


def landsatComposite(resultsWorkspace):
    print("\n\nCommencing Composite Operation...".upper())
    reflectanceFolder = os.path.join(resultsWorkspace, "SurfaceReflectance")
    CompositeFolder = os.path.join(resultsWorkspace, "Composites")
    os.makedirs(CompositeFolder, exist_ok=True)
    print("Composite Save  Directory Created\n\n")
    for path, dirs, files in os.walk(reflectanceFolder):
        for directory in dirs:
            compWorkspace = os.path.join(path, directory)
            print(compWorkspace)
            try:
                arcpy.env.workspace = compWorkspace
                arcpy.env.overwriteOutput = True
                compFile = ((os.path.split(compWorkspace))[-1].split("_"))
                compFileName = "Scene" + compFile[2] + "_" + compFile[3] + "_composite.tif"
                print(compFileName)
                outFileSave = os.path.join(CompositeFolder, compFileName)
                RefCorrBands = arcpy.ListRasters(raster_type="TIF")
                print("Running Band Composite...")
                arcpy.CompositeBands_management(in_rasters=RefCorrBands, out_raster=outFileSave)
                print("Composite Completed\n")
            except IOError:
                print("Error Accessing File")
    print("\n\nAll Operations Complete".upper())


removeGapMaskDir()
