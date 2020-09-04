import os
import arcpy    # Arcpy 3.8 (Arcpy Pro)
import shutil
import pathlib
from arcpy.sa import *
from itertools import chain

"""Perform Brightness Temperature, Land Surface Temperature and Composite on VIS-IR Bands For Landsat Sensors 5,7 and 8.
No correction for Landsat 7 SLC Error (Ensure to Delete gap_mask folder Within Landsat 7 Folders).
To Use, Create a folder Named 'Uncompress' and DUMP All your landsat Scene folder within it
The Uncompress folder should be in the same root directory as this python file."""

bandGainsValue = 0
bandOffsetValue = 0
bandK1Value = 0
bandK2Value = 0


def landsatPreProcess():
    ResultsFolder = pathlib.Path(os.path.join(os.path.dirname(__file__), "Processed"))
    os.makedirs(ResultsFolder, exist_ok=True)
    print("Results Folder Created\n")
    workingDir = pathlib.Path(os.path.join(os.path.dirname(__file__), 'Uncompress'))
    for root, folders, files in os.walk(workingDir):
        for folder in folders:
            SceneDir = os.path.join(root, folder)
            try:
                print(SceneDir)
                arcpy.env.workspace = SceneDir
                arcpy.env.overwriteOutput = True
                Scene = ((os.path.split(SceneDir))[-1])
                TempSceneFolder = Scene + "_Temperature"
                TempSavePath = os.path.join(ResultsFolder, "SceneTemperature",  TempSceneFolder)
                os.makedirs(TempSavePath, exist_ok=True)
                print("Save Directory for Temperature Outputs Created")
                arcpy.CheckOutExtension("spatial")
                metadata = arcpy.ListFiles(wild_card="*MTL.txt")
                metaDir = os.path.join(workingDir, SceneDir, metadata[0])
                newMetaDir = os.path.join(TempSavePath, metadata[0])
                print("Copied Metadata to ", TempSavePath)
                shutil.copy2(metaDir, newMetaDir)
                if Scene.startswith("LC08"):
                    l8 = arcpy.ListRasters(raster_type="TIF")
                    VisIRTir8 = list(chain(l8[5:7], l8[1:3]))
                    for band8 in VisIRTir8:
                        ret_name = band8.split("_")
                        bandName8 = "Scene_" + ret_name[2] + "_" + ret_name[3] + "_" + ret_name[7].strip(
                            ".TIF") + "_TOARad.tif"
                        Correction(SceneDir, band8, bandName8, TempSavePath)
                elif Scene.startswith("LE07"):
                    l7 = arcpy.ListRasters(raster_type="TIF")
                    VisIRTir7 = list(chain(l7[2:4], l7[5:7]))
                    for band7 in VisIRTir7:
                        ret_name = band7.split("_")
                        if band7.__contains__("B6"):
                            bandName7 = "Scene_" + ret_name[2] + "_" + ret_name[3] + "_" + ret_name[7] + "_" + \
                                        ret_name[-1].strip(".TIF") + "_TOARad.tif"
                            Correction(SceneDir, band7, bandName7, TempSavePath)
                        else:
                            bandName7 = "Scene_" + ret_name[2] + "_" + ret_name[3] + "_" + ret_name[7].strip(".TIF") \
                                        + "_TOARad.tif"
                            Correction(SceneDir, band7, bandName7, TempSavePath)
                elif Scene.startswith("LT05") or Scene.startswith("LT04"):
                    l54 = arcpy.ListRasters(raster_type="TIF")
                    bands54 = list(chain(l54[2:4], [l54[5]]))
                    for band54 in bands54:
                        ret_name = band54.split("_")
                        bandName54 = "Scene_" + ret_name[2] + "_" + ret_name[3] + "_" + ret_name[7].strip(
                            ".TIF") + "_TOARad.tif"
                        Correction(SceneDir, band54, bandName54, TempSavePath)
                else:
                    print(Scene, " May Not Be a Valid Landsat Scene Folder or May not Contain Thermal Bands\n")
            except WindowsError:
                print("Folder Already Exists")
    NDVI_Emissivity(ResultsFolder)


def Correction(env, band, saveName, saveDir):
    arcpy.CheckOutExtension('Spatial')
    readGains(env, band)
    band_RefMul = bandGainsValue
    readOffset(env, band)
    band_RefAdd = bandOffsetValue
    print("{0} has a Gain and Offset Values of {1} & {2} Respectively".format(band, band_RefMul, band_RefAdd))
    print("Setting NoData Value and Executing Radiometric Calibration...")
    arcpy.SetRasterProperties_management(band, nodata="1 0")
    bandNom_P1 = arcpy.sa.Times(band, band_RefMul)
    TOARad = arcpy.sa.Plus(bandNom_P1, band_RefAdd)
    OutRadName = (os.path.join(saveDir, saveName))
    TOARad.save(OutRadName)
    print("Top of Atmosphere Radiance for " + band + " Saved\n")


def readGains(curWorkspace, layer):
    global bandGainsValue
    layerSplit = layer.split("_")
    bandValue = str(layerSplit[-1].lstrip("B").strip(".TIF"))
    bandValue7 = str(layerSplit[-3].lstrip("B") + "_VCID_" + layerSplit[-1].strip(".TIF"))
    for root, directory, files in os.walk(curWorkspace):
        for file in files:
            if file.endswith("MTL.txt"):
                metadata = os.path.join(root, file)
                with open(metadata, "r") as MTL:
                    if layer.__contains__("LE07" and "B6"):
                        for line in MTL:
                            if line.__contains__("RADIANCE_MULT_BAND_" + bandValue7):
                                bandGainsRow = line.strip()
                                bandGainsValue = float(bandGainsRow.split("=")[1])
                                return bandGainsValue
                    else:
                        for line in MTL:
                            if line.__contains__("RADIANCE_MULT_BAND_" + bandValue):
                                bandGainsRow = line.strip()
                                bandGainsValue = float(bandGainsRow.split("=")[1])
                                return bandGainsValue
                MTL.close()


def readOffset(curWorkspace, layer):
    global bandOffsetValue
    layerSplit = layer.split("_")
    bandValue = str(layerSplit[-1].lstrip("B").strip(".TIF"))
    bandValue7 = str(layerSplit[-3].lstrip("B") + "_VCID_" + layerSplit[-1].strip(".TIF"))
    for root, directory, files in os.walk(curWorkspace):
        for file in files:
            if file.endswith("MTL.txt"):
                metadata = os.path.join(root, file)
                with open(metadata, "r") as MTL:
                    if layer.__contains__("LE07" and "B6"):
                        for line in MTL:
                            if line.__contains__("RADIANCE_ADD_BAND_" + bandValue7):
                                bandOffsetRow = line.strip()
                                bandOffsetValue = float(bandOffsetRow.split("=")[1])
                                return bandOffsetValue
                    else:
                        for line in MTL:
                            if line.__contains__("RADIANCE_ADD_BAND_" + bandValue):
                                bandOffsetRow = line.strip()
                                bandOffsetValue = float(bandOffsetRow.split("=")[1])
                                return bandOffsetValue
                MTL.close()


def NDVI_Emissivity(ProcessedWorkspace):
    TempWorkspace = os.path.join(ProcessedWorkspace, "SceneTemperature")
    for path, dirs, files in os.walk(TempWorkspace):
        for directory in dirs:
            LstWorkSpace = os.path.join(path, directory)
            print("\n\n", LstWorkSpace)
            try:
                arcpy.env.workspace = LstWorkSpace
                arcpy.env.overwriteOutput = True
                arcpy.CheckOutExtension("spatial")
                if directory.__contains__("LC08"):
                    layers8 = arcpy.ListRasters(wild_card="*TOARad*", raster_type="TIF")
                    VisIR8 = layers8[2:]
                    TIR8 = layers8[0:2]
                    computeBrightTemp(LstWorkSpace, TIR8)
                    computeNDVIEmissivity(directory, VisIR8)
                elif directory.__contains__("LE07"):
                    layers7 = arcpy.ListRasters(wild_card="*TOARad*", raster_type="TIF")
                    VisIR7 = layers7[0:2]
                    TIR7 = layers7[2:]
                    computeBrightTemp(LstWorkSpace, TIR7)
                    computeNDVIEmissivity(directory, VisIR7)
                else:
                    layers54 = arcpy.ListRasters(wild_card="*TOARad*", raster_type="TIF")
                    VisIR54 = layers54[0:2]
                    TIR54 = layers54[2:]
                    computeBrightTemp(LstWorkSpace, TIR54)
                    computeNDVIEmissivity(directory, VisIR54)
            except IOError:
                print("Error")
    LandSurfaceTemperature(TempWorkspace)


def computeNDVIEmissivity(ndviWorkspace, VisIRBands):
    print("Calculating NDVI...")
    NIRBand = Raster(VisIRBands[1])
    RedBand = Raster(VisIRBands[0])
    ndviNom = arcpy.sa.Minus(NIRBand, RedBand)
    ndviDenom = arcpy.sa.Plus(NIRBand, RedBand)
    ndvi = Divide(ndviNom, ndviDenom)
    splitName = ndviWorkspace.split("_")
    emissivityName = "Scene_" + splitName[2] + "_" + splitName[3] + "_Emissivity.tif"
    ndviMin = float((arcpy.GetRasterProperties_management(in_raster=ndvi, property_type="MINIMUM")).getOutput(0))
    ndviMax = float((arcpy.GetRasterProperties_management(in_raster=ndvi, property_type="MAXIMUM")).getOutput(0))
    print("Scene has Minimum and Maximum NDVI Values of {0} & {1} Respectively".format(ndviMin, ndviMax))
    print("Calculating Proportion of Vegetation and Emissivity...")
    vegPropNom = Minus(ndvi, ndviMin)
    vegPropDenom = Minus(ndviMax, ndviMin)
    vegProp = Power(Divide(vegPropNom, vegPropDenom), 2)
    emissivity1 = Times(float(0.004), vegProp)
    emissivity = Plus(emissivity1, float(0.986))
    emissivity.save(emissivityName)
    print("Emissivity Saved as ", emissivityName)
    return emissivity


def computeBrightTemp(brightTempWorkspace, TIRBands):
    print("Calculating Brightness Temperature...")
    for tempBand in TIRBands:
        read_K1(brightTempWorkspace, tempBand)
        band_K1 = bandK1Value
        read_K2(brightTempWorkspace, tempBand)
        band_K2 = bandK2Value
        print("{0} has a K1 and K2 Constant Values of {1} & {2} Respectively".format(tempBand, band_K1, band_K2))
        BTName = str(tempBand.replace("TOARad", "BrightTemp_K"))
        BT_Denom1 = Divide(band_K1, tempBand)
        BT_Denom2 = Plus(BT_Denom1, 1)
        BT_Denom = Ln(BT_Denom2)
        BrightTemp = band_K2/BT_Denom
        OutBTName = (os.path.join(brightTempWorkspace, BTName))
        BrightTemp.save(OutBTName)
        print("Brightness Temperature Saved for " + tempBand + "\n")


def read_K1(curWorkspace, layer):
    global bandK1Value
    layerSplit = layer.split("_")
    K1Value = str(layerSplit[-2].lstrip("B"))
    K1Value7 = str(layerSplit[-3].lstrip("B") + "_VCID_" + layerSplit[-2])
    for root, directory, files in os.walk(curWorkspace):
        for file in files:
            if file.endswith("MTL.txt"):
                metadata = os.path.join(root, file)
                with open(metadata, "r") as MTL:
                    if curWorkspace.__contains__("LE07"):
                        for line in MTL:
                            if line.__contains__("K1_CONSTANT_BAND_" + K1Value7):
                                bandK1Row = line.strip()
                                bandK1Value = float(bandK1Row.split("=")[1])
                                return bandK1Value
                    else:
                        for line in MTL:
                            if line.__contains__("K1_CONSTANT_BAND_" + K1Value):
                                bandK1Row = line.strip()
                                bandK1Value = float(bandK1Row.split("=")[1])
                                return bandK1Value
                MTL.close()


def read_K2(curWorkspace, layer):
    global bandK2Value
    layerSplit = layer.split("_")
    K2Value = str(layerSplit[-2].lstrip("B"))
    K2Value7 = str(layerSplit[-3].lstrip("B") + "_VCID_" + layerSplit[-2])
    for root, directory, files in os.walk(curWorkspace):
        for file in files:
            if file.endswith("MTL.txt"):
                metadata = os.path.join(root, file)
                with open(metadata, "r") as MTL:
                    if curWorkspace.__contains__("LE07"):
                        for line in MTL:
                            if line.__contains__("K2_CONSTANT_BAND_" + K2Value7):
                                bandK2Row = line.strip()
                                bandK2Value = float(bandK2Row.split("=")[1])
                                return bandK2Value
                    else:
                        for line in MTL:
                            if line.__contains__("K2_CONSTANT_BAND_" + K2Value):
                                bandK2Row = line.strip()
                                bandK2Value = float(bandK2Row.split("=")[1])
                                return bandK2Value
                MTL.close()


def LandSurfaceTemperature(finalWorkspace):
    for root, directories, files in os.walk(finalWorkspace):
        for directory in directories:
            workspace = os.path.join(root, directory)
            print("\n\n", workspace)
            try:
                arcpy.env.workspace = workspace
                arcpy.env.overwriteOutput = True
                arcpy.CheckOutExtension("spatial")
                folderSplit = directory.split("_")
                LSTName = "Scene_" + folderSplit[2] + "_" + folderSplit[3] + "_TempK.tif"
                BTLayers = arcpy.ListRasters(wild_card="*BrightTemp*")
                emissivity = arcpy.ListRasters(wild_card="*Emissivity*")
                pConstant = 14380
                if workspace.__contains__("LC08"):
                    LST8_layers = []
                    radianceWavelengths = [10.8, 12]
                    for layer, radiance in zip(BTLayers, radianceWavelengths):
                        print("Calculating Land Surface Temperature for {0} using Emitted Radiance Wavelength of {1}"
                              .format(layer, radiance))
                        LST_part1 = Divide(layer, pConstant)
                        LST_part2 = Times(float(radiance), LST_part1)
                        LST_part3 = Ln(emissivity[0])
                        LST_part4 = Times(LST_part2, LST_part3)
                        LST_part5 = Plus(1, LST_part4)
                        LST = Divide(layer, LST_part5)
                        LST8_layers.append(LST)
                    print("Calculating the Average Land Surface Temperature of the 2 Bands")
                    averageLST = CellStatistics(LST8_layers, statistics_type="MEAN")
                    averageLST.save(LSTName)
                    print("Saved LST Layer\n")
                elif workspace.__contains__("LE07"):
                    LST7_layers = []
                    radiance7 = 11.5
                    for layer in BTLayers:
                        print("Calculating Land Surface Temperature for {0} using Emitted Radiance Wavelength of {1}"
                              .format(layer, radiance7))
                        LST_part1 = Divide(layer, pConstant)
                        LST_part2 = Times(float(radiance7), LST_part1)
                        LST_part3 = Ln(emissivity[0])
                        LST_part4 = Times(LST_part2, LST_part3)
                        LST_part5 = Plus(1, LST_part4)
                        LST = Divide(layer, LST_part5)
                        LST7_layers.append(LST)
                    averageLST = CellStatistics(LST7_layers, statistics_type="MEAN")
                    print("Calculating the Average Land Surface Temperature of the 2 Bands")
                    averageLST.save(LSTName)
                    print("Saved LST Layer\n")
                else:
                    radiance54 = 11.5
                    ("Calculating Land Surface Temperature for {0} using Emitted Radiance Wavelength of {1}"
                     .format(BTLayers[0], radiance54))
                    LST_part1 = Divide(BTLayers[0], pConstant)
                    LST_part2 = Times(float(radiance54), LST_part1)
                    LST_part3 = Ln(emissivity[0])
                    LST_part4 = Times(LST_part2, LST_part3)
                    LST_part5 = Plus(1, LST_part4)
                    LST = Divide(BTLayers[0], LST_part5)
                    LST.save(LSTName)
                    print("Saved LST Layer\n")
            except IndexError:
                print("Index out of Range")
    print("all lst computation operation completed".upper())


landsatPreProcess()
