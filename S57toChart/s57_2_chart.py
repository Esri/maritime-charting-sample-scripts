#-------------------------------------------------------------------------------
# Name:        s57_to_chart.py
# Purpose:
#
# Author:      Brooke Reams and Patricia Sheatsley
# Created:     November 3, 2016
# Release:     10.5
#-------------------------------------------------------------------------------

import arcpy, arcpyproduction, os, sys, traceback, shutil, re, smtplib, ConfigParser

class ex(Exception):
    def __init__(self, value):
        self.parameter = value
    def __str__(self):
        return repr(self.parameter)


CUR_DIR = sys.path[0]
NAUT_FDS = "Nautical"
CARTO_FDS = "CartographicFeatures"
DF_NAME = "Layers"
ZOC_DATAFRAME = "ZOC diagram"

CARTO_FCS = ['TracksA_L', 'SeabedA_L', 'RegulatedA_L', 'PortsA_L', 'OffshoreA_L', 'MilitaryA_L', 'DangersA_L',
            'LightSectorsL', 'IceA_L', 'DepthsA_L', 'NaturalA_L']
NAUT_FCS = ['OffshoreInstallationsP', 'MetaDataL', 'MetaDataA', 'RegulatedAreasAndLimitsA', 'RegulatedAreasAndLimitsP',
'           RegulatedAreasAndLimitsL', 'CoastlineA', 'CoastlineP', 'CoastlineL', 'NaturalFeaturesA', 'NaturalFeaturesL',
            'NaturalFeaturesP', 'CulturalFeaturesP', 'CulturalFeaturesL', 'CulturalFeaturesA', 'PortsAndServicesA',
            'PortsAndServicesL', 'PortsAndServicesP', 'SoundingsP', 'DepthsA', 'MilitaryFeaturesP', 'MilitaryFeaturesA',
            'IceFeaturesA', 'AidsToNavigationP', 'TracksAndRoutesP', 'TracksAndRoutesL', 'TracksAndRoutesA', 'MetaDataP',
            'OffshoreInstallationsA', 'OffshoreInstallationsL', 'DepthsL', 'DangersA', 'DangersP', 'DangersL', 'SeabedA',
            'SeabedP', 'SeabedL', 'TidesAndVariationsP', 'TidesAndVariationsL', 'TidesAndVariationsA']

#User-defined parameters
input_fldr = arcpy.GetParameterAsText(0)
chart_schema = arcpy.GetParameterAsText(1)
template_mxd = arcpy.GetParameterAsText(2)
REF_SCALE = arcpy.GetParameterAsText(3)
output_fldr = arcpy.GetParameterAsText(4)


##input_fldr = r'C:\Data\S57toChart\InputCells'
##chart_schema = r'C:\Data\S57toChart\Templates\ChartSchemaTemplate.gdb'
##template_mxd = r'C:\Data\S57toChart\Templates\ChartTemplate.mxd'
##REF_SCALE = '50000'
##output_fldr = r'C:\Data\S57toChart\Output'

def getAOI(prod_db):
    # Set workspace
    arcpy.env.workspace = prod_db
    # Get MetaDataA fc
    meta_fc = getFC(prod_db, "MetaDataA", NAUT_FDS)
    if meta_fc:
        # Make feature layer where FCSUBTYPE = M_NSYS
        where = "FCSUBTYPE = 35"
        arcpy.MakeFeatureLayer_management(meta_fc, "meta_lyr", where)
        # Dissolve layer into one feature
        arcpy.AddMessage("\tDissolving area of interest into one feature")
        aoi = "in_memory\\aoi"
        arcpy.Dissolve_management("meta_lyr", aoi, multi_part="SINGLE_PART")
        arcpy.MakeFeatureLayer_management(aoi, "aoi")
        return "aoi"

    else:
        raise ex("MetaDataA feature class not found in " + prod_db)


def getDesktopFolder():
    # Get install info
    install_info = arcpy.GetInstallInfo()
    # Get Version
    version = install_info["Version"]
    folder_version = version.split(".")[0] + "." + version.split(".")[1]
    # Create desktop folder path
    desktop_fldr = os.path.join(os.path.dirname(os.path.dirname(install_info["InstallDir"])), "MaritimeCharting", "Desktop" + folder_version)
    return desktop_fldr


def cartoLimits(aoi, prod_db, desktop_fldr):
    # Subtype field used in where clause to filter inputs to Model
    subtype_fld = arcpy.AddFieldDelimiters(prod_db, "FCSubtype")

    # Make feature layer of aoi
    arcpy.MakeFeatureLayer_management(aoi, "aoi")
    # Convert AOI to polyline
    aoi_line = os.path.join(arcpy.env.scratchGDB, "aoi_line")
    arcpy.FeatureToLine_management("aoi", aoi_line)
    arcpy.MakeFeatureLayer_management(aoi_line, "aoi_line")

    # Get list of input feature classes, subtypes, and cart limit feature classes
    inputs = [["DangersA", [], "DangersA_L"],
              ["DepthsA", ["5", "10", "15"], "DepthsA_L"],
              ["IceFeaturesA", [], "IceA_L"],
              ["MilitaryFeaturesA", [], "MilitaryA_L"],
              ["NaturalFeaturesA", ["1", "20", "35"], "NaturalA_L"],
              ["OffshoreInstallationsA", [], "OffshoreA_L"],
              ["PortsAndServicesA", ["5", "10", "25", "30", "35", "40", "45", "50", "55", "60", "65", "70", "80"], "PortsA_L"],
              ["RegulatedAreasAndLimitsA", ["1", "5", "10", "15", "20", "30", "40", "50", "60", "65", "70", "75", "85", "95", "105", "110", "115"], "RegulatedA_L"],
              ["SeabedA", ["15"], "SeabedA_L"],
              ["TracksAndRoutesA", ["1", "5", "10", "15", "20", "25", "40", "45", "70"], "TracksA_L"]]

    # Set workspace
    arcpy.env.workspace = prod_db

    # Get CoastlineA and CloastlineL layers
    coastlinea_fc = getFC(prod_db, "CoastlineA", NAUT_FDS)
    arcpy.MakeFeatureLayer_management(coastlinea_fc, "CoastlineA")
    coastlinel_fc = getFC(prod_db, "CoastlineL", NAUT_FDS)
    arcpy.MakeFeatureLayer_management(coastlinel_fc, "CoastlineL")

    # Loop through list of inputs
    for data in inputs:
        # Get full paths to data
        input_fc = getFC(prod_db, data[0], NAUT_FDS)
        output_fc = getFC(prod_db, data[2], CARTO_FDS)
        if input_fc != "" and output_fc != "":
            # Check if there are subtypes, if there are, write where clause
            where = ""
            if len(data[1]) > 0:
                where = subtype_fld + " = "
                where = where + (" OR " + subtype_fld + " = ").join(data[1])
                # Remove single quotes that get added to beginning and end of where clause
                where = where.replace("'", "")
            # Select features in where clause
            arcpy.MakeFeatureLayer_management(input_fc, "in_lyr", where)
            # Only run Generate Cartographic Limits model if layer has features
            if int(arcpy.GetCount_management("in_lyr").getOutput(0)) > 0:
                arcpy.AddMessage("\t\t" + data[2])
                arcpy.GenerateCartographicLimits_nautical("in_lyr", "CoastlineL; CoastlineA; aoi_line", output_fc)

    return



def getFC(ws, fc_name, fds=""):
    fc_list = arcpy.ListFeatureClasses("*" + fc_name, feature_dataset=fds)
    if not fc_list:
        fc = ""
        arcpy.AddWarning(fc_name + " not found in " + ws + ".")
    else:
        fc = os.path.join(ws, fds, fc_list[0])
    return fc



def maskCoastlineConflicts(prod_db, desktop_fldr):
    arcpy.AddMessage("\tMasking coastline and bridges")
    # Subtype field used in where clause to access bridges in CulturalFeaturesA
    subtype_fld = arcpy.AddFieldDelimiters(prod_db, "FCSubtype")
    # Get subtype of Bridge
    bridge = "5"
    # Define spatial reference
    sr = arcpy.SpatialReference(4326)

    # Get CoastlineL and CulturalFeaturesA layers
    coastlinel_fc = getFC(prod_db, "CoastlineL", NAUT_FDS)
    culturalfeaturesa_fc = getFC(prod_db, "CulturalFeaturesA", NAUT_FDS)

    # Only continue if CoastlineL and CulturalFeaturesA layers are in the TOC
    if coastlinel_fc != "" and culturalfeaturesa_fc != "":
        # Make feature layer form CoastlineL
        arcpy.MakeFeatureLayer_management(coastlinel_fc, "coastlinel_lyr")
        # Make feature layer of bridge features
        where = subtype_fld + " = " + bridge
        arcpy.MakeFeatureLayer_management(culturalfeaturesa_fc, "bridges", where)
        # Check if there are any bridge features in the layer
        if int(arcpy.GetCount_management("bridges").getOutput(0)) > 0:
            # Run Intersecting Layers Mask GP tool to create mask poly where coastline intersect bridges
            mask_fc = os.path.join(prod_db, CARTO_FDS, "MASK_CoastlineL")
            arcpy.IntersectingLayersMasks_cartography("bridges", "coastlinel_lyr", mask_fc, REF_SCALE, sr, "0.01 POINTS")

    return



def main():
    try:
        # Check for Nautical extension
        if arcpy.CheckExtension("Nautical") == "Available":
            arcpy.CheckOutExtension("Nautical")
        else:
            raise ex("Maritime: Charting license is unavailable.")

        # Overwrite existing output
        arcpy.env.overwriteOutput = 1

        # Get Desktop install info for install path and version
        desktop_fldr = getDesktopFolder()

        # Create output folder if doesn't already exist
        if not os.path.exists(output_fldr):
            os.mkdir(output_fldr)


        # Get list of original S57 files (.000) from folder
        s57_list = [os.path.join(input_fldr, f) for f in os.listdir(input_fldr) if os.path.splitext(f)[1] == ".000"]
        arcpy.AddMessage(str(s57_list))
        print s57_list

        processed_list = []
        # Loop through .000 files in folder
        for s57_file in s57_list:
            # Get name of S57 file
            s57_name = os.path.splitext(os.path.basename(s57_file))[0]
            arcpy.AddMessage(s57_name)
            print s57_name
            processed_list.append(os.path.basename(s57_file))

            # Make copy of template chart gdb
            output_gdb = os.path.join(output_fldr, s57_name + ".gdb")
            arcpy.AddMessage("\tCopying chart schema...")
            print "\tCopying Chart Schema"
            arcpy.Copy_management(chart_schema, output_gdb)

            # Find update files
            update_list = [os.path.join(input_fldr, f) for f in os.listdir(input_fldr) if os.path.splitext(f)[0] == s57_name and os.path.splitext(f)[1] != ".000" and re.search(".[0-9][0-9][0-9]", os.path.splitext(f)[1])]

            # Import S57 to gdb
            print "\tImporting " + s57_name
            arcpy.AddMessage("\tImporting S-57 cell and updates...")
            arcpy.ImportS57ToGeodatabase_nautical(s57_file, output_gdb, update_list)

            # Retrieve aoi
            arcpy.AddMessage("\tFinding area of interest...")
            print "\tRetrieving AOI"
            aoi = getAOI(output_gdb)

            # Create a new map document to be used for converting labels to anno
            map_doc = os.path.join(output_fldr, s57_name + ".mxd")
            arcpy.AddMessage("\tCopying and naming map document...")
            shutil.copy(template_mxd, map_doc)

            # Chart automation
            print "\tRunning Chart Automation tool"
            arcpy.AddMessage("\tChart automation tool...\n\t\tAdd layers to TOC, create grids, generate light sectors, generate cartographic limits, calculate symbology, convert labels to annotation")
            arcpy.ChartAutomation_nautical("'Add Layers to TOC'; 'Generate Light Sectors';'Calculate Symbology';'Create Grids and Graticules'; 'Generate Cartographic Limits';'Convert Labels to Annotation'", REF_SCALE, output_gdb, "PATH_TO_MXD", map_doc, aoi, DF_NAME)
            #ZOC diagram tool
            print "\tRunning Create ZOC diagram tool"
            arcpy.AddMessage("\tCreating zone of confidence diagram...")
            arcpy.CreateZOCDiagram_nautical(aoi, (int(REF_SCALE)*10), output_gdb, "PATH_TO_MXD", map_doc, ZOC_DATAFRAME)
            #Creating map document object for ZOC diagram
            arcpy.AddMessage("\tUpdating data frame properties...")
            mxd = arcpy.mapping.MapDocument(map_doc)
            #Get list of data frames in map document object for zoc diagram
            zoc_df = arcpy.mapping.ListDataFrames(mxd, "ZOC diagram")[0]
            #Find grid feature dataset, list the grids then create object
            gridFDS = os.path.join(output_gdb,"GRD_Grids")
            gridObj = arcpyproduction.mapping.ListGrids(gridFDS,"ZOC*")[0]
            #Update zoc diagram dataframe properties
            gridObj.updateDataFrameProperties(zoc_df)#, zoc_df.extent.polygon)
            arcpy.RefreshActiveView()
            arcpy.RefreshTOC()
            
            mxd.save()

    except ex, (instance):
        arcpy.AddError(instance.parameter)
        print instance.parameter

    except arcpy.ExecuteError:
        # Get the geoprocessing error messages
        msgs = arcpy.GetMessage(0)
        msgs += arcpy.GetMessages(2)

        # Return gp error messages for use with a script tool
        arcpy.AddError(msgs)
        print msgs

    except:
        # Get the traceback object
        tb = sys.exc_info()[2]
        tbinfo = traceback.format_tb(tb)[0]

        # Concatenate information together concerning the error into a message string
        pymsg = tbinfo + "\n" + str(sys.exc_type)+ ": " + str(sys.exc_value)

        # Return python error messages for use with a script tool
        arcpy.AddError(pymsg)
        print pymsg


if __name__ == '__main__':
    main()

arcpy.AddMessage("\tS-57 to chart completed")
print "\tENC to chart completed"