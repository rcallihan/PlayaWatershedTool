#version fixes. Iterate through each pour point. 
import arcpy, os, time, sys, traceback, exceptions, re
from arcpy import env
from arcpy.sa import *
arcpy.CheckOutExtension("Spatial")
arcpy.CheckOutExtension("3D")
arcpy.env.overwriteOutput = True

#Get user parameters
OutputLocation = arcpy.GetParameterAsText(0)
PlayaPolys = arcpy.GetParameterAsText(1)
HUC_DEM = arcpy.GetParameterAsText(2)

# OutputLocation = r"C:\Users\IEUser\Desktop\playafiles\WatershedTest"
# PlayaPolys = r"C:\Users\IEUser\Desktop\playafiles\PlayaTestIterate.shp"
# HUC_DEM = r"C:\Users\IEUser\Desktop\playafiles\lidar_huc12_extract1.img"

# WorkspaceGBD = "PlayaTemp.gdb"

#create a temp file geodatabase to run all processes.
arcpy.AddMessage("======================================")
arcpy.AddMessage("Starting playa watershed tool")
arcpy.AddMessage("======================================")  
#arcpy.AddMessage('Creating temp geodatabase in %s...' % OutputLocation)
# PlayaWorkspace = os.path.join(OutputLocation, WorkspaceGBD)
# if arcpy.Exists(PlayaWorkspace):
# 	arcpy.AddMessage("Removing previous temp geodatabase")
# 	arcpy.Delete_management(PlayaWorkspace)
# arcpy.CreateFileGDB_management(OutputLocation, WorkspaceGBD)

#initial environment parameters
arcpy.env.workspace = OutputLocation
arcpy.env.snapRaster = HUC_DEM
arcpy.env.extent = HUC_DEM

#Gets cell size from the input DEM. Cellsize is used to set buffer width of playa boundary and other raster cell sizes. 
CellSizeResult = arcpy.GetRasterProperties_management(HUC_DEM, "CELLSIZEX")
Cellsize = CellSizeResult.getOutput(0) 
RastCellSize = Cellsize + " Meters"
loopcount = 0

arcpy.MakeFeatureLayer_management(PlayaPolys, "playa_layer")
arcpy.AddField_management("playa_layer", "Playa_ID", "SHORT")
PlayaCount = int(arcpy.GetCount_management("playa_layer").getOutput(0))

fc = "playa_layer"
field = "OBJECTID"
cursor = arcpy.SearchCursor(fc)
row = cursor.next()
while row:
	t0 = time.clock()
	playaID = row.getValue(field)
	playaIDstr = str(playaID)
	playaname = "Playa_" + playaIDstr
	rastname = "rast_" + playaname
	WatershedName = "Shed_" + playaIDstr
	loopcount = loopcount + 1

	arcpy.AddMessage("======================================")
	arcpy.AddMessage("Creating watershed for playa %s of %s" % (loopcount, PlayaCount))
	arcpy.AddMessage("======================================")

	PlayaPolysLayer = "playa_layer"
	query = '"OBJECTID" = ' + str(playaID)
	
	#Selects iterative rows in the feature layer, converts to raster.
	arcpy.AddMessage("Rasterizing playas...") 
	arcpy.SelectLayerByAttribute_management("playa_layer", "NEW_SELECTION", query)
	arcpy.CalculateField_management("playa_layer", "Playa_ID", playaID)
	arcpy.env.extent = ""
	arcpy.PolygonToRaster_conversion("playa_layer", "Playa_ID", "playa_rast", "CELL_CENTER", "NONE", Cellsize)
	
	# Punches playas out of DEM. More specifically, nullifies cells in the DEM that are NOT Null in the "playa_rast"
	arcpy.AddMessage("Removing playa from the DEM...")
	arcpy.env.extent = HUC_DEM 
	outraster = SetNull(~(IsNull("playa_rast")), HUC_DEM)
	outraster.save("punched_DEM")

	#fill DEM
	arcpy.AddMessage("Filling sinks...")
	outFill = Fill("punched_DEM")
	outFill.save("filled_DEM")

	# Process: FlowDirection
	arcpy.AddMessage("Calculating DEM flow direction...")
	outFlowDirection = FlowDirection(outFill, "NORMAL", "")
	outFlowDirection.save("Fill_flowdir")

	################
	
	#Buffers the playa boundry and converts to raster
	arcpy.AddMessage("Buffering playa by %s " % (RastCellSize))
	arcpy.env.extent = ""
	arcpy.Buffer_analysis(PlayaPolysLayer, "single_playa_poly_buff.shp", RastCellSize, "FULL", "ROUND", "NONE", "")
	arcpy.AddMessage("Creating and rasterizing playa boundary (i.e. pour points)")
	arcpy.FeatureToLine_management("single_playa_poly_buff.shp", "single_playa_buff_line.shp", "", "ATTRIBUTES")
	arcpy.PolylineToRaster_conversion("single_playa_buff_line.shp", "Playa_ID", "buff_perim", "MAXIMUM_LENGTH", "NONE", HUC_DEM)

	#Creates a watershed for playa boundary (pour points) and converts to a vector. 
	arcpy.AddMessage("Creating watershed from playa pour points")
	PlayaBoundary = "buff_perim"
	FlowDir = "Fill_flowdir"
	arcpy.env.extent = HUC_DEM
	outWatershed = Watershed(FlowDir, PlayaBoundary, "VALUE")
	outWatershed.save("watershed")
	arcpy.RasterToPolygon_conversion("watershed", WatershedName, "NO_SIMPLIFY", "VALUE")

	#calculate volume under polygon
	# try:
	# 	arcpy.DeleteField_management(Gulley_Boundary_Polygon, "Volume")
	# 	arcpy.FeatureToRaster_conversion(Gulley_Boundary_Polygon, "FID", "Gully_Mask_Raster.img", Cellsize)

	# 	#Convert Poly verticies to points, extract raster value to poly points, convert poly to raster
	# 	arcpy.FeatureVerticesToPoints_management(Gulley_Boundary_Polygon, "Gulley_Boundary_Points.shp", "ALL")
	# 	ExtractValuesToPoints("Gulley_Boundary_Points.shp", Elevation_Raster, "Gully_Points_with_Elevation.shp", "NONE", "VALUE_ONLY")

	# 	output_tin = OutputLocation + "/Poly_Boundary_Tin"
	# 	arcpy.CreateTin_3d(output_tin, sr, "Gully_Points_with_Elevation.shp RASTERVALU masspoints", "DELAUNAY")

	# 	#Tin to raster
	# 	TinRastCellSize = "CELLSIZE " + Cellsize
	# 	arcpy.TinRaster_3d(output_tin, "cap_raster", "FLOAT", "", TinRastCellSize, "")

	# 	#sets elevation pixels outside of polygon of interest to null.  
	# 	outElevationraster = SetNull((IsNull("Gully_Mask_Raster.img")), Elevation_Raster)
	# 	#Ignore pixels with negative depth values
	# 	outDepthraster = Con("cap_raster" > outElevationraster, "cap_raster" - outElevationraster)
		
	# 	#calculates volume above raster, adds output to the poly shp
	# 	arcpy.SurfaceVolume_3d(outDepthraster, '', 'ABOVE')
	# 	result = arcpy.GetMessages()
	# 	volume = float(re.findall(r'Volume= *([\d\.]+)', result)[0])
	# 	arcpy.AddField_management(Gulley_Boundary_Polygon, "Volume", "FLOAT", "15", "4")
	# 	arcpy.CalculateField_management(Gulley_Boundary_Polygon, "Volume", float(volume))
	# 	print volume
		
	# 	#cleaning up intermediate files
	# 	print "cleaning"
	# 	for filename in ["Gulley_Boundary_Points.shp", "Gully_Mask_Raster.img", "Gully_Points_with_Elevation.shp", outElevationraster, outDepthraster, "cap_raster", output_tin]:
	# 		if arcpy.Exists(filename):
	# 			arcpy.Delete_management(filename)
	# 	arcpy.AddMessage("Done cleaning intermediate files.")


	# except arcpy.ExecuteError:
	# 	print arcpy.GetMessages()

	#calculating and reporting process time
	arcpy.AddMessage("Watershed created for playa %s, process took %s minutes." % (loopcount, int((time.clock() - t0)/60)))
	arcpy.AddMessage("Approximately %s minutes remaining." % (int((time.clock() - t0)/60)*(PlayaCount - loopcount)+1))
	print playaname

	for filename in ["playa_rast", "filled_DEM", "punched_DEM", "Fill_flowdir", "buff_perim"]:
		if arcpy.Exists(filename):
			arcpy.Delete_management(filename)

	row = cursor.next()



#Searches for all individual watershed features and merges them together.
arcpy.AddMessage("======================================")
arcpy.AddMessage("Successfully created all %s watersheds." % (PlayaCount))
arcpy.AddMessage("======================================")
arcpy.AddMessage("Merging individual watershed polygons into Playa_Watersheds.shp...")  
datasetList = arcpy.ListFeatureClasses("Shed_*", "Polygon")
arcpy.Merge_management(datasetList, "Playa_Watersheds.shp")

#Adds a field in the merged watershed layer that links back to original Playa ID.
arcpy.AddMessage("Calculating fields...") 
arcpy.AddField_management("Playa_Watersheds.shp", "Playa_ID", "SHORT")
arcpy.CalculateField_management("Playa_Watersheds.shp", "Playa_ID", "!GRIDCODE!", "PYTHON_9.3")
arcpy.DeleteField_management("Playa_Watersheds.shp", ["GRIDCODE", "ID"])
#arcpy.FeatureClassToShapefile_conversion("Playa_Watersheds.shp", OutputLocation)



#Cleanup: Deletes all uneeded featers from geodatabase
arcpy.AddMessage("Cleaning up intermediate files...")
for filename in ["single_playa_poly_buff.shp", "single_playa_buff_line", "single_playa_buff_line.shp", "playa_buff_perim", "playa_rast", "punched_DEM", "filled_DEM", "DEM_Filled_flowdir", "Playa_watershed", "watershed"]:
	if arcpy.Exists(filename):
		arcpy.Delete_management(filename)
	print "Deleting intermediate files"
for f in datasetList:
	arcpy.Delete_management(f)
arcpy.AddMessage("Done cleaning intermediate files.")

arcpy.AddMessage("======================================")
arcpy.AddMessage("Done!")
arcpy.AddMessage("======================================")