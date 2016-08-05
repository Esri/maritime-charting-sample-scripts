"""
s57_to_product.py
Esri - Database Services
Brooke Reams, breams@esri.com
July 7, 2016
- Creates an S-57 product in the Product Library for each input .000.
- Imports multiple enc base and update files from a folder into an NIS schema.

Updates:

"""


import arcpy, sys, os, traceback, re


try:
    # Get user params
    fldr = arcpy.GetParameterAsText(0)
    pl = arcpy.GetParameterAsText(1)
    series = arcpy.GetParameterAsText(2) ## "Nautical::ENC::ENC"
    target_wrkspc = arcpy.GetParameterAsText(3)

    # Initialize list to store path to all base cells used to create products in PL
    base_cells = []

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
                    base_cells.append(base_cell)
                    # Run Import S-57 to Geodatabase GP tool on base cell and update cells
                    arcpy.AddMessage("\t" + file)
                    if update_cells:
                        arcpy.AddMessage("\t\t" + "\n\t\t".join([os.path.basename(cell) for cell in update_cells]))
                    try:
                        arcpy.ImportS57ToGeodatabase_nautical(base_cell, update_cells, target_wrkspc)
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
                            base_cells.append(base_cell)
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
                        arcpy.ImportS57ToGeodatabase_nautical(base_cell, update_cells_sorted, target_wrkspc)
                    except:
                        msgs = arcpy.GetMessage(0)
                        msgs += arcpy.GetMessages(2)
                        arcpy.AddWarning(msgs)


    # Create S-57 product for each base cell
    arcpy.AddMessage("Creating products in Product Library:")
    for enc in base_cells:
        arcpy.AddMessage("\t" + enc)
        try:
            arcpy.CreateS57Product_nautical(in_s57_cell=enc, in_pl_workspace=pl, in_pl_series=series)
        except:
            msgs = arcpy.GetMessage(0)
            msgs += arcpy.GetMessages(2)
            arcpy.AddWarning(msgs)


    # Set target workspace as output
    arcpy.SetParameterAsText(4, target_wrkspc)


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
