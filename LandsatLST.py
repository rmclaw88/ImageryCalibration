import os
import arcpy    # Arcpy 3.8 (Arcpy Pro)
import shutil
import tarfile
import pathlib
from arcpy.sa import *
from itertools import chain

"""Calculate Brightness Temperature and Land Surface Temperature in Kelvin on Landsat Sensors (TM, ETM+ and OLI).
To Use, Create a folder Named 'Compress' and DUMP compressed Landsat data within
The 'Compress' folder should be in the same root directory as this python file."""

GainsOffset = {}
bandKConstant = {}


def uncompress():
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
                    arcpy.CheckOutExtension("spatial")
                    Scene = ((os.path.split(SceneDir))[-1])
                    TempSceneFolder = Scene + "_Temperature"
                    TempSavePath = os.path.join(ResultsFolder, "SceneTemperature", TempSceneFolder)
                    metadata = arcpy.ListFiles(wild_card="*MTL.txt")
                    if Scene.startswith("LC08"):
                        makeDir(TempSavePath, SceneDir, metadata)
                        l8 = arcpy.ListRasters(raster_type="TIF")
                        VisIRTir8 = list(chain(l8[5:7], l8[1:3]))
                        for band8 in VisIRTir8:
                            ret_name = band8.split("_")
                            bandName8 = "Scene_" + ret_name[2] + "_" + ret_name[3] + "_" + ret_name[7].strip(
                                ".TIF") + "_TOARad.tif"
                            Correction(SceneDir, band8, bandName8, TempSavePath)
                    elif Scene.startswith("LE07"):
                        makeDir(TempSavePath, SceneDir, metadata)
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
                        makeDir(TempSavePath, SceneDir, metadata)
                        l54 = arcpy.ListRasters(raster_type="TIF")
                        bands54 = list(chain(l54[2:4], [l54[5]]))
                        for band54 in bands54:
                            ret_name = band54.split("_")
                            bandName54 = "Scene_" + ret_name[2] + "_" + ret_name[3] + "_" + ret_name[7].strip(
                                ".TIF") + "_TOARad.tif"
                            Correction(SceneDir, band54, bandName54, TempSavePath)
                    else:
                        print("Landsat Scene Does Not Contain any Thermal Bands\nSkipped!!!\n")
                except WindowsError:
                    print("Folder Already Exists")
    BrightTemp_Emissivity(ResultsFolder)


def makeDir(OutputPath, SceneFolder, metaFile):
    os.makedirs(OutputPath, exist_ok=True)
    print("Save Directory for Temperature Outputs Created")
    metaDir = os.path.join(SceneFolder, metaFile[0])
    newMetaDir = os.path.join(OutputPath, metaFile[0])
    shutil.copy2(metaDir, newMetaDir)
    print("Metadata Exported\n")


def Correction(env, band, saveName, saveDir):
    bandSplit = band.split("_")
    bandValue = str(bandSplit[-1].lstrip("B").strip(".TIF"))
    bandValueL7 = str(bandSplit[-3].lstrip("B") + "_VCID_" + bandSplit[-1].strip(".TIF"))
    readGainsOffSet(env, band, bandValue, bandValueL7)
    G_OValues = []
    if band.__contains__("LE07") and band.__contains__("B6"):
        G_OValues.append(GainsOffset["RADIANCE_MULT_BAND_" + bandValueL7])
        G_OValues.append(GainsOffset["RADIANCE_ADD_BAND_" + bandValueL7])
    else:
        G_OValues.append(GainsOffset["RADIANCE_MULT_BAND_" + bandValue])
        G_OValues.append(GainsOffset["RADIANCE_ADD_BAND_" + bandValue])
    print("{0} has a Gain and Offset Values of {1} & {2} Respectively".format(band, G_OValues[0], G_OValues[1]))
    print("Setting NoData Value and Executing Radiometric Calibration...")
    arcpy.SetRasterProperties_management(band, nodata="1 0")
    bandNom_P1 = Times(band, G_OValues[0])
    TOARad = Plus(bandNom_P1, G_OValues[1])
    OutRadName = os.path.join(saveDir, saveName)
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
                    if layer.__contains__("LE07") and layer.__contains__("B6"):
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


def BrightTemp_Emissivity(ProcessedWorkspace):
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
    ndviNom = Minus(NIRBand, RedBand)
    ndviDenom = Plus(NIRBand, RedBand)
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
        OutBTName = os.path.join(brightTempWorkspace, BTName)
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
    LSTDir = os.path.join(finalWorkspace, "LST_DATA")
    os.makedirs(LSTDir, exist_ok=True)
    print("LST Save Directory Created\n")
    for root, directories, files in os.walk(finalWorkspace):
        for directory in directories:
            if not directory.__contains__("LST_DATA"):
                workspace = os.path.join(root, directory)
                print(workspace)
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
                            computeLST(layer, radiance, pConstant, Emissivity,  LST8_layers)
                        print("Calculating the Average Land Surface Temperature of the 2 Bands...")
                        averageLST8 = CellStatistics(LST8_layers, statistics_type="MEAN")
                        averageLST8.save(os.path.join(LSTDir, LSTName))
                        print("Saved LST Layer\n")
                    elif workspace.__contains__("LE07"):
                        LST7_layers = []
                        radiance7 = 11.5
                        for layer in BTLayers:
                            computeLST(layer, radiance7, pConstant, Emissivity, LST7_layers)
                        averageLST7 = CellStatistics(LST7_layers, statistics_type="MEAN")
                        print("Calculating the Average Land Surface Temperature of the 2 Bands...")
                        averageLST7.save(os.path.join(LSTDir, LSTName))
                        print("Saved LST Layer\n")
                    else:
                        radiance54 = 11.5
                        LST54_Layers = []
                        computeLST(BTLayers[0], radiance54, pConstant, Emissivity, LST54_Layers)
                        LST54 = LST54_Layers[0]
                        LST54.save(os.path.join(LSTDir, LSTName))
                        print("Saved LST Layer\n")
                except IndexError:
                    print("Index out of Range\n")
    print("\nall lst computation operation completed".upper())


def computeLST(BTLayer, rad, planckConstant, emissivity, compLIST):
    print("Calculating Land Surface Temperature for {0} using Emitted Radiance Wavelength of {1}..."
          .format(BTLayer, rad))
    LST_part1 = Divide(BTLayer, planckConstant)
    LST_part2 = Times(float(rad), LST_part1)
    LST_part4 = Plus(1, Times(LST_part2, Ln(emissivity)))
    LST = Divide(BTLayer, LST_part4)
    compLIST.append(LST)


uncompress()