
import arcpy, os
from arcpy import env
from arcpy.sa import *
arcpy.CheckOutExtension("Spatial")
arcpy.env.overwriteOutput = True

#Get user parameters
OutputLocation = arcpy.GetParameterAsText(0)
PlayaPolys = arcpy.GetParameterAsText(1)
HUC_DEM = arcpy.GetParameterAsText(2)

# OutputLocation = r"C:\Users\IEUser\Desktop\playafiles"
# PlayaPolys = r"C:\Users\IEUser\Desktop\playafiles\PlayaTestIterate.shp"
# HUC_DEM = r"C:\Users\IEUser\Desktop\playafiles\lidar_huc12_extract1.img"

WorkspaceGBD = "PlayaNonNested.gdb"

#create a temp file geodatabase to run all processes.
arcpy.AddMessage("======================================")
arcpy.AddMessage("Starting playa watershed tool")
arcpy.AddMessage("======================================") 
arcpy.AddMessage('Creating temp geodatabase in %s...' % OutputLocation)
PlayaWorkspace = os.path.join(OutputLocation, WorkspaceGBD)
if arcpy.Exists(PlayaWorkspace):
	print "Deleting previous workspace geodatabase"
	arcpy.Delete_management(PlayaWorkspace)
arcpy.CreateFileGDB_management(OutputLocation, WorkspaceGBD)

#initial environment parameters
arcpy.env.workspace = PlayaWorkspace
arcpy.env.snapRaster = HUC_DEM
arcpy.env.extent = HUC_DEM

#HUC_DEM = "lidar_huc12_extract"

#Gets cell size from the input DEM. Cellsize is used to set buffer width of playa boundary and other raster cell sizes. 
CellSizeResult = arcpy.GetRasterProperties_management(HUC_DEM, "CELLSIZEX")
Cellsize = CellSizeResult.getOutput(0) 
RastCellSize = Cellsize + " Meters" 

arcpy.MakeFeatureLayer_management(PlayaPolys, "playa_layer")
#arcpy.AddField_management("playa_layer", "Playa_ID", "SHORT")
#arcpy.CalculateField_management("playa_layer", "Playa_ID", "!OBJECTID!", "PYTHON_9.3")
#PlayaCount = int(arcpy.GetCount_management("playa_layer").getOutput(0))


#Buffers the playa boundry and converts to raster
arcpy.AddMessage("Buffering playa polygons by %s " % (RastCellSize))
arcpy.Buffer_analysis("playa_layer", "single_playa_poly_buff", RastCellSize, "FULL", "ROUND", "NONE", "")
arcpy.AddMessage("Creating and rasterizing playa boundary (i.e. pour points)")
arcpy.FeatureToLine_management("single_playa_poly_buff", "single_playa_buff_line", "", "ATTRIBUTES")
arcpy.PolylineToRaster_conversion("single_playa_buff_line", "OBJECTID", "playa_buff_perim", "MAXIMUM_LENGTH", "NONE", HUC_DEM)

#arcpy.env.snapRaster = "lidar_huc12_extract"
arcpy.env.extent = HUC_DEM

#Converts playa poly to raster to be punched from DEM
arcpy.AddMessage("Rasterizing playas...") 
arcpy.PolygonToRaster_conversion(PlayaPolys, "OBJECTID", "playa_rast", "CELL_CENTER", "NONE", HUC_DEM)

# Process: Punches playas out of DEM.
arcpy.AddMessage("Removing playa from the DEM...") 
outraster = SetNull(~(IsNull("playa_rast")), HUC_DEM)
outraster.save("punched_DEM")

#fill DEM
arcpy.AddMessage("Filling sinks...")
outFill = Fill("punched_DEM")
outFill.save("filled_DEM")

# Process: FlowDirection
arcpy.AddMessage("Calculating DEM flow direction...")
outFlowDirection = FlowDirection(outFill, "NORMAL", "")
outFlowDirection.save("DEM_Filled_flowdir")

#MakeWatershed
PlayaBoundary = "playa_buff_perim"
FlowDir = "DEM_Filled_flowdir"
arcpy.AddMessage("Creating watershed from playa pour points...") 
outWatershed = Watershed("DEM_Filled_flowdir", "playa_buff_perim", "VALUE")
outWatershed.save("Playa_watershed")

arcpy.AddMessage("Converting watershed raster to vector...") 
arcpy.RasterToPolygon_conversion("Playa_watershed", "Playa_Watersheds", "NO_SIMPLIFY", "VALUE")
arcpy.AddMessage("Calculating fields...") 
arcpy.AddField_management("Playa_Watersheds", "Playa_ID", "SHORT")
arcpy.CalculateField_management("Playa_Watersheds", "Playa_ID", "!GRIDCODE!", "PYTHON_9.3")
arcpy.DeleteField_management("Playa_Watersheds", ["GRIDCODE", "ID"])
arcpy.FeatureClassToShapefile_conversion("Playa_Watersheds", OutputLocation)

arcpy.AddMessage("Cleaning up intermediate files...")
for filename in ["single_playa_poly_buff", "single_playa_buff_line", "playa_buff_perim", "playa_rast", "punched_DEM", "filled_DEM", "DEM_Filled_flowdir", "Playa_watershed"]:
	if arcpy.Exists(filename):
		arcpy.Delete_management(filename)
	print "Deleting intermediate files"
arcpy.Delete_management(PlayaWorkspace)
arcpy.AddMessage("Done cleaning intermediate files.")

arcpy.AddMessage("======================================")
arcpy.AddMessage("Done!")
arcpy.AddMessage("======================================")




