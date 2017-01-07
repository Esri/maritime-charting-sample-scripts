"""
s57_to_gis.py
Esri - Database Services
Brooke Reams, breams@esri.com
December 15, 2016 edit for 10.5 and 10.5.1 
- Imports multiple enc base and update files from a folder into an NIS schema.
- Calculates symbology on NIS database.
- Re-sources layers in map document.

Updates:

"""


import arcpy, sys, os, traceback, re


try:
    # Get user params
    fldr = arcpy.GetParameterAsText(0)
    target_wrkspc = arcpy.GetParameterAsText(1)
    map_doc = arcpy.GetParameterAsText(2)


    # Check for Nautical extension
    if arcpy.CheckExtension("Nautical") == "Available":
        arcpy.CheckOutExtension("Nautical")
    else:
        arcpy.AddError("Maritime: Charting license is unavailable.")


    # Loop through ENC files in folder and run S-57 to GDB on base cell and associated udpate cells
    arcpy.AddMessage("Importing ENCs to NIS:")
    for root, dirs, files in os.walk(fldr):
        for file in files:
            if file.endswith(".000"):
                # Handle NOAA ENCs and exclude international exchange sets - these are handled in else
                if os.path.basename(root) != "0":
                    update_cells = []
                    for item in os.listdir(root):
                        if not re.search(".000$", item) and re.search(".[0-9][0-9][0-9]$", item):
                            update_cells.append(os.path.join(root, item))
                    update_cells.sort()
                    base_cell = os.path.join(root, file)
                    # Run Import S-57 to Geodatabase GP tool on base cell and update cells
                    arcpy.AddMessage("\t" + file)
                    if update_cells:
                        arcpy.AddMessage("\t\t" + "\n\t\t".join([os.path.basename(cell) for cell in update_cells]))
                    try:
                        arcpy.ImportS57ToGeodatabase_nautical(base_cell, target_wrkspc, update_cells)
                    except:
                        msgs = arcpy.GetMessage(0)
                        msgs += arcpy.GetMessages(2)
                        arcpy.AddWarning(msgs)
                # Handle international exchange sets
                else:
                    # Get base cell
                    for item in os.listdir(root):
                        if re.search(".000$", item):
                            base_cell = os.path.join(root, item)
                            update_cells = []
                    # Get update cells
                    pre_root = os.path.dirname(root)
                    for root2, dirs2, files2 in os.walk(pre_root):
                        if root2 != pre_root and os.path.basename(root2) != "0":
                            for item in os.listdir(root2):
                                if not re.search(".000$", item) and re.search(".[0-9][0-9][0-9]$", item):
                                    update_cells.append((root2, item))
                    sorted_list = sorted(update_cells, key=lambda cell: cell[1]) 
                    update_cells_sorted = []
                    for cell in sorted_list:
                        update_cells_sorted.append(os.path.join(cell[0], cell[1]))
                    # Run Import S-57 to Geodatabase GP tool on base cell and update cells
                    arcpy.AddMessage("\t" + item)
                    if update_cells_sorted:
                        arcpy.AddMessage("\t\t" + "\n\t\t".join([os.path.basename(cell) for cell in update_cells_sorted]))
                    try:
                        arcpy.ImportS57ToGeodatabase_nautical(base_cell, target_wrkspc, update_cells_sorted)
                    except:
                        msgs = arcpy.GetMessage(0)
                        msgs += arcpy.GetMessages(2)
                        arcpy.AddWarning(msgs)

    
    # Get all feature class names in NIS and feature classes to calculate
    all_fcs = []
    calc_fcs = []
    arcpy.env.workspace = target_wrkspc
    for fds in arcpy.ListDatasets(feature_type="Feature"):
        for fc in arcpy.ListFeatureClasses(feature_dataset=fds):
            all_fcs.append(fc.split(".")[-1])
            if not fc.lower().startswith("plts") and not fc.lower().startswith("user"):
                calc_fcs.append(fc.split(".")[-1])

    # Calculate symbology on target workspace (NIS)
    arcpy.AddMessage("Calculating symbology")
    arcpy.CalculateSymbology_nautical("S-52", calc_fcs, "true")


    # Check workspace type of target workspace
    desc_workspace_type = arcpy.Describe(target_wrkspc).workspaceType
    if desc_workspace_type == "LocalDatabase":
        if os.path.splitext(target_wrkspc)[-1] == ".gdb":
            workspace_type = "FILEGDB_WORKSPACE"
        else:
            workspace_type = "ACCESS_WORKSPACE"
    else:
        workspace_type = "SDE_WORKSPACE"

    # Re-source layers in map document
    arcpy.AddMessage("Re-sourcing layers in map document")
    # Get map document object and layers in map document
    mxd = arcpy.mapping.MapDocument(map_doc)
    lyrs_list = [lyr for lyr in arcpy.mapping.ListLayers(mxd) if lyr.supports("DATASETNAME")]
    # Re-source layer if there is a matching dataset name in the target workspace (NIS)
    for lyr in lyrs_list:
        dataset_name = lyr.datasetName.split(".")[-1]
        if dataset_name in all_fcs:
            lyr.replaceDataSource(target_wrkspc, workspace_type, dataset_name, False)

    # Zoom map extent to first MetaDataA layer in the TOC with features
    df = mxd.activeDataFrame
    metadata_lyrs = arcpy.mapping.ListLayers(mxd, "MetaDataA")
    for lyr in metadata_lyrs:
        if int(arcpy.GetCount_management(lyr).getOutput(0)) > 0:
            arcpy.SelectLayerByAttribute_management(lyr, "NEW_SELECTION")
            df.zoomToSelectedFeatures()
            arcpy.SelectLayerByAttribute_management(lyr, "CLEAR_SELECTION")
            break

    
    # Save the map document
    arcpy.AddMessage("Saving map document")
    mxd.save()

    # Set target workspace as output
    arcpy.SetParameterAsText(3, target_wrkspc)


except arcpy.ExecuteError:
    # Get the geoprocessing error messages
    msgs = arcpy.GetMessage(0)
    msgs += arcpy.GetMessages(2)

    # Return gp error messages for use with a script tool
    arcpy.AddError(msgs)

except:
    # Get the traceback object
    tb = sys.exc_info()[2]
    tbinfo = traceback.format_tb(tb)[0]

    # Concatenate information together concerning the error into a message string
    pymsg = tbinfo + "\n" + str(sys.exc_type)+ ": " + str(sys.exc_value)

    # Return python error messages for use with a script tool
    arcpy.AddError(pymsg)
