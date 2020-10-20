import os
import math
import arcpy    # Arcpy 3.8 (Arcpy Pro)
import shutil
import tarfile
import pathlib
from itertools import chain

"""To Use, Create a folder Named 'Compress' and DUMP All Compressed Landsat data within it.
The Compress folder should be in the same root directory as this python file.
Converts Digital Number to Surface Reflectance (Radiometric Calibration & Atmospheric Correction).
Executes Composites/ Band Stacking on the Visible-InfraRed Bands.
Only for Landsat Sensor Data (MSS, TM, ETM+ and OLI). No protocol to fill Landsat 7 Scan Line Error"""

sunElev = 0
GainsOffset = {}


def Uncompress():
    currentDirectory = pathlib.Path(os.path.join(os.path.dirname(__file__), 'Compress'))
    for currentFile in currentDirectory.iterdir():
        try:
            uncompress_path = os.path.join(os.path.dirname(__file__),
                                           'Uncompress/%s' % (currentFile.name.replace('.tar.gz', '')))
            os.makedirs(uncompress_path, exist_ok=False)
            print('UNZIPPING\t', currentFile, '\nINTO\t\t', uncompress_path, '\n')
            tar_ref = tarfile.open(currentFile, 'r')
            tar_ref.extractall(uncompress_path)
            tar_ref.close()
        except IOError:
            print('cannot unzip file, folder %s already exist' % currentFile.name)
    landsatPreProcess()


def landsatPreProcess():
    ResultsFolder = pathlib.Path(os.path.join(os.path.dirname(__file__), "Processed"))
    os.makedirs(ResultsFolder, exist_ok=True)
    print("\n\nStarting Radiometric and Atmospheric Correction...\nResults Folder Created\n")
    workingDir = pathlib.Path(os.path.join(os.path.dirname(__file__), 'Uncompress'))
    for root, folders, files in os.walk(workingDir):
        for folder in folders:
            if folder.startswith('gap_mask'):
                gapMaskDir = os.path.join(root, folder)
                shutil.rmtree(gapMaskDir)
                print(gapMaskDir, " Deleted")
            else:
                SceneDir = os.path.join(root, folder)
                try:
                    print(SceneDir)
                    arcpy.env.workspace = SceneDir
                    arcpy.env.overwriteOutput = True
                    Scene = ((os.path.split(SceneDir))[-1])
                    RefSceneFolder = Scene + "_Preprocessed"
                    RefSavePath = os.path.join(ResultsFolder, "SurfaceReflectance",  RefSceneFolder)
                    os.makedirs(RefSavePath, exist_ok=True)
                    print("Surface Reflectance Directory for ", folder, " Created")
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
                    elif Scene.startswith("LM04") or Scene.startswith("LM05"):
                        l45 = arcpy.ListRasters(raster_type="TIF")
                        visIR45 = l45[0:4]
                        for band45 in visIR45:
                            print(band45)
                            Correction(SceneDir, band45, radiance_cor, RefSavePath)
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
    bandMinVal = float((arcpy.GetRasterProperties_management(in_raster=bandCor, property_type="MINIMUM")).getOutput(0))
    bandStdVal = float((arcpy.GetRasterProperties_management(in_raster=bandCor, property_type="STD")).getOutput(0))
    bandThreshold = float(bandMinVal + bandStdVal)
    print("{0} has a Minimum, StdDev and Threshold values of {1}, {2} & {3} Respectively".
          format(band, bandMinVal, bandStdVal, bandThreshold))
    band_refCor = arcpy.sa.Minus(bandCor, bandThreshold)
    print("Saving Surface Reflectance Output...\n")
    OutRefName = (os.path.join(saveDir, bandName))
    band_refCor.save(OutRefName)


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


Uncompress()