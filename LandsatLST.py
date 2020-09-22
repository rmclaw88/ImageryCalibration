import os
import arcpy    # Arcpy 3.8 (Arcpy Pro)
import shutil
import pathlib
from arcpy.sa import *
from itertools import chain

"""Perform Brightness Temperature, Land Surface Temperature and Composite on VIS-IR Bands For Landsat Sensors 5,7 and 8.
To Use, Create a folder Named 'Uncompress' and DUMP All your landsat Scene folder within it
The Uncompress folder should be in the same root directory as this python file."""

GainsOffset = {}
bandKConstant = {}


def landsatPreProcess():
    ResultsFolder = pathlib.Path(os.path.join(os.path.dirname(__file__), "Processed"))
    os.makedirs(ResultsFolder, exist_ok=True)
    print("\n\nResults Folder Created\n")
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
                    TempSceneFolder = Scene + "_Temperature"
                    TempSavePath = os.path.join(ResultsFolder, "SceneTemperature",  TempSceneFolder)
                    os.makedirs(TempSavePath, exist_ok=True)
                    print("Save Directory for Temperature Outputs Created")
                    arcpy.CheckOutExtension("spatial")
                    metadata = arcpy.ListFiles(wild_card="*MTL.txt")
                    metaDir = os.path.join(workingDir, SceneDir, metadata[0])
                    newMetaDir = os.path.join(TempSavePath, metadata[0])
                    print("Metadata Exported")
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
                                bandName7 = "Scene_" + ret_name[2] + "_" + ret_name[3] + "_" + \
                                            ret_name[7].strip(".TIF") + "_TOARad.tif"
                                Correction(SceneDir, band7, bandName7, TempSavePath)
                    elif Scene.startswith("LT05") or Scene.startswith("LT04"):
                        l54 = arcpy.ListRasters(raster_type="TIF")
                        bands54 = list(chain(l54[2:4], [l54[5]]))
                        for band54 in bands54:
                            ret_name = band54.split("_")
                            bandName54 = "Scene_" + ret_name[2] + "_" + ret_name[3] + "_" + ret_name[7].strip(
                                ".TIF") + "_TOARad.tif"
                            Correction(SceneDir, band54, bandName54, TempSavePath)
                except WindowsError:
                    print("Folder Already Exists")
    NDVI_Emissivity(ResultsFolder)


def Correction(env, band, saveName, saveDir):
    bandSplit = band.split("_")
    bandValue = str(bandSplit[-1].lstrip("B").strip(".TIF"))
    bandValueL7 = str(bandSplit[-3].lstrip("B") + "_VCID_" + bandSplit[-1].strip(".TIF"))
    readGainsOffSet(env, band, bandValue, bandValueL7)
    G_OValues = []
    if band.__contains__("LE07" and "B6"):
        G_OValues.append(GainsOffset["RADIANCE_MULT_BAND_" + bandValueL7])
        G_OValues.append(GainsOffset["RADIANCE_ADD_BAND_" + bandValueL7])
    else:
        G_OValues.append(GainsOffset["RADIANCE_MULT_BAND_" + bandValue])
        G_OValues.append(GainsOffset["RADIANCE_ADD_BAND_" + bandValue])
    print("{0} has a Gain and Offset Values of {1} & {2} Respectively".format(band, G_OValues[0], G_OValues[1]))
    print("Setting NoData Value and Executing Radiometric Calibration...")
    arcpy.SetRasterProperties_management(band, nodata="1 0")
    bandNom_P1 = arcpy.sa.Times(band, G_OValues[0])
    TOARad = arcpy.sa.Plus(bandNom_P1, G_OValues[1])
    OutRadName = (os.path.join(saveDir, saveName))
    TOARad.save(OutRadName)
    G_OValues.clear()
    print("Top of Atmosphere Radiance for " + band + " Saved\n")


def readGainsOffSet(curWorkspace, layer, layerValue, LayerValue7):
    global GainsOffset
    for root, directory, files in os.walk(curWorkspace):
        for file in files:
            if file.endswith("MTL.txt"):
                metadata = os.path.join(root, file)
                with open(metadata, "r") as MTL:
                    if layer.__contains__("LE07" and "B6"):
                        for line in MTL:
                            if line.__contains__("RADIANCE_MULT_BAND_" + LayerValue7) or \
                                    line.__contains__("RADIANCE_ADD_BAND_" + LayerValue7):
                                RowL7 = line.strip().split("=")
                                GainsOffset[RowL7[0].strip()] = float(RowL7[1])
                    else:
                        for line in MTL:
                            if line.__contains__("RADIANCE_MULT_BAND_" + layerValue) or \
                                    line.__contains__("RADIANCE_ADD_BAND_" + layerValue):
                                Row = line.strip().split("=")
                                GainsOffset[Row[0].strip()] = float(Row[1])
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
        layerSplit = tempBand.split("_")
        bandKValue = str(layerSplit[-2].lstrip("B"))
        bandKValue7 = str(layerSplit[-3].lstrip("B") + "_VCID_" + layerSplit[-2])
        readKConstants(brightTempWorkspace, bandKValue, bandKValue7)
        kValues = []
        if brightTempWorkspace.__contains__("LE07"):
            kValues.append(bandKConstant["K1_CONSTANT_BAND_" + bandKValue7])
            kValues.append(bandKConstant["K2_CONSTANT_BAND_" + bandKValue7])
        else:
            kValues.append(bandKConstant["K1_CONSTANT_BAND_" + bandKValue])
            kValues.append(bandKConstant["K2_CONSTANT_BAND_" + bandKValue])
        print("{0} has a K1 and K2 Constant Values of {1} & {2} Respectively".format(tempBand, kValues[0], kValues[1]))
        BTName = str(tempBand.replace("TOARad", "BrightTemp_K"))
        BT_Denom1 = Divide(kValues[0], tempBand)
        BT_Denom2 = Plus(BT_Denom1, 1)
        BT_Denom = Ln(BT_Denom2)
        BrightTemp = Divide(kValues[1], BT_Denom)
        OutBTName = (os.path.join(brightTempWorkspace, BTName))
        BrightTemp.save(OutBTName)
        kValues.clear()
        print("Brightness Temperature Saved for " + tempBand + "\n")


def readKConstants(curWorkspace, KValue, KValue7):
    global bandKConstant
    for root, directory, files in os.walk(curWorkspace):
        for file in files:
            if file.endswith("MTL.txt"):
                metadata = os.path.join(root, file)
                with open(metadata, "r") as MTL:
                    if curWorkspace.__contains__("LE07"):
                        for line in MTL:
                            if line.__contains__("K1_CONSTANT_BAND_" + KValue7) or \
                                    line.__contains__("K2_CONSTANT_BAND_" + KValue7):
                                k7ConstantRow = line.strip().split("=")
                                bandKConstant[k7ConstantRow[0].strip()] = float(k7ConstantRow[1])
                    else:
                        for line in MTL:
                            if line.__contains__("K1_CONSTANT_BAND_" + KValue) or \
                                    line.__contains__("K2_CONSTANT_BAND_" + KValue):
                                kConstantRow = line.strip().split("=")
                                bandKConstant[kConstantRow[0].strip()] = float(kConstantRow[1])
                MTL.close()


def LandSurfaceTemperature(finalWorkspace):
    for root, directories, files in os.walk(finalWorkspace):
        for directory in directories:
            workspace = os.path.join(root, directory)
            print("\n", workspace)
            try:
                arcpy.env.workspace = workspace
                arcpy.env.overwriteOutput = True
                arcpy.CheckOutExtension("spatial")
                folderSplit = directory.split("_")
                LSTName = "Scene_" + folderSplit[2] + "_" + folderSplit[3] + "_TempK.tif"
                BTLayers = arcpy.ListRasters(wild_card="*BrightTemp*")
                emissivityLayer = arcpy.ListRasters(wild_card="*Emissivity*")
                Emissivity = emissivityLayer[0]
                pConstant = 14380
                if workspace.__contains__("LC08"):
                    LST8_layers = []
                    radianceWavelengths = [10.8, 12]
                    for layer, radiance in zip(BTLayers, radianceWavelengths):
                        computeLST(layer, radiance, pConstant, Emissivity, LST8_layers)
                    print("Calculating the Average Land Surface Temperature of the 2 Bands...")
                    averageLST = CellStatistics(LST8_layers, statistics_type="MEAN")
                    averageLST.save(LSTName)
                    print("Saved LST Layer")
                elif workspace.__contains__("LE07"):
                    LST7_layers = []
                    radiance7 = 11.5
                    for layer in BTLayers:
                        computeLST(layer, radiance7, pConstant, Emissivity, LST7_layers)
                    averageLST7 = CellStatistics(LST7_layers, statistics_type="MEAN")
                    print("Calculating the Average Land Surface Temperature of the 2 Bands...")
                    averageLST7.save(LSTName)
                    print("Saved LST Layer")
                else:
                    radiance54 = 11.5
                    LST54_Layers = []
                    computeLST(BTLayers[0], radiance54, pConstant, Emissivity, LST54_Layers)
                    LST54 = LST54_Layers[0]
                    LST54.save(LSTName)
                    print("Saved LST Layer")
            except IndexError:
                print("Index out of Range")
    print("all lst computation operation completed".upper())


def computeLST(BTLayer, rad, planckConstant, emissivity, compLIST):
    print("Calculating Land Surface Temperature for {0} using Emitted Radiance Wavelength of {1}..."
          .format(BTLayer, rad))
    LST_part1 = Divide(BTLayer, planckConstant)
    LST_part2 = Times(float(rad), LST_part1)
    LST_part3 = Ln(emissivity)
    LST_part4 = Times(LST_part2, LST_part3)
    LST_part5 = Plus(1, LST_part4)
    LST = Divide(BTLayer, LST_part5)
    compLIST.append(LST)


landsatPreProcess()