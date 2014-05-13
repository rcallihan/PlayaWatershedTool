
import arcpy, os, re
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

#create a temp file geodatabase to run all processes.
arcpy.AddMessage("======================================")
arcpy.AddMessage("Starting playa watershed tool")
arcpy.AddMessage("======================================") 

#initial environment parameters
arcpy.env.workspace = OutputLocation
arcpy.env.snapRaster = HUC_DEM
arcpy.env.extent = HUC_DEM


#HUC_DEM = "lidar_huc12_extract"
PlayaPolysLayer = "playa_layer"
loopcount = 0 

#Gets cell size from the input DEM. Cellsize is used to set buffer width of playa boundary and other raster cell sizes. 
CellSizeResult = arcpy.GetRasterProperties_management(HUC_DEM, "CELLSIZEX")
Cellsize = CellSizeResult.getOutput(0) 
RastCellSize = Cellsize + " Meters" 
RastCellSize_adj = str(float(int(Cellsize) * .90)) + " Meters"
sr = arcpy.Describe(HUC_DEM).spatialReference

arcpy.AddMessage("Cellsize %s" % (CellSizeResult))
arcpy.AddMessage("RastCellsize adf %s" % (RastCellSize_adj))

#add volume and playa_Id fields to poly layer.
arcpy.MakeFeatureLayer_management(PlayaPolys, PlayaPolysLayer)
PlayaCount = int(arcpy.GetCount_management(PlayaPolysLayer).getOutput(0))
arcpy.DeleteField_management(PlayaPolysLayer, "Volume")
arcpy.AddField_management(PlayaPolysLayer, "Volume", "FLOAT", "15", "4")
arcpy.AddField_management(PlayaPolysLayer, "Playa_ID", "SHORT")

#Buffers the playa boundry and converts to raster
arcpy.AddMessage("Buffering playa polygons by %s " % (RastCellSize_adj))
arcpy.Buffer_analysis(PlayaPolysLayer, "single_playa_poly_buff.shp", RastCellSize_adj, "FULL", "ROUND", "NONE", "")
arcpy.AddMessage("Creating and rasterizing playa boundary (i.e. pour points)")
arcpy.FeatureToLine_management("single_playa_poly_buff.shp", "single_playa_buff_line.shp", "", "ATTRIBUTES")
arcpy.PolylineToRaster_conversion("single_playa_buff_line.shp", "FID", "buff_perim", "MAXIMUM_LENGTH", "", CellSizeResult)

#arcpy.env.snapRaster = "lidar_huc12_extract"
arcpy.env.extent = HUC_DEM

#Converts playa poly to raster to be punched from DEM
arcpy.AddMessage("Rasterizing playas...") 
arcpy.PolygonToRaster_conversion(PlayaPolys, "FID", "playa_rast", "CELL_CENTER", "NONE", HUC_DEM)

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
outFlowDirection.save("flowdir")

#MakeWatershed
arcpy.AddMessage("Creating watershed from playa pour points...") 
outWatershed = Watershed("flowdir", "buff_perim", "VALUE")
outWatershed.save("watershed")

arcpy.AddMessage("Converting watershed raster to vector...") 
arcpy.RasterToPolygon_conversion(outWatershed, "Playa_Watersheds.shp", "SIMPLIFY", "VALUE")
arcpy.AddMessage("Calculating fields...") 
arcpy.AddField_management("Playa_Watersheds.shp", "Playa_ID", "SHORT")
arcpy.CalculateField_management("Playa_Watersheds.shp", "Playa_ID", "!GRIDCODE!", "PYTHON_9.3")
arcpy.DeleteField_management("Playa_Watersheds.shp", ["GRIDCODE", "ID"])

#calculate playa volume
arcpy.AddMessage("Calculating Volume...")

field = "FID"
cursor = arcpy.SearchCursor(PlayaPolysLayer)
row = cursor.next()
while row:
	t0 = time.clock()
	playaID = row.getValue(field)
	playaIDstr = str(playaID)
	playaname = "Playa_" + playaIDstr
	#rastname = "rast_" + playaname
	WatershedName = "Shed_" + playaIDstr
	loopcount = loopcount + 1

	arcpy.AddMessage("======================================")
	arcpy.AddMessage("Calculating volume for playa %s of %s" % (loopcount, PlayaCount))
	arcpy.AddMessage("======================================")
	
	#Selects iterative rows in the feature layer, converts to raster.
	query = '"FID" = ' + str(playaID)
	arcpy.AddMessage("Rasterizing playas...") 
	arcpy.SelectLayerByAttribute_management(PlayaPolysLayer, "NEW_SELECTION", query)
	arcpy.CalculateField_management(PlayaPolysLayer, "Playa_ID", playaID)

	###############################
	#calculate volume under polygon
	arcpy.AddMessage("Calculating Volume...")
	arcpy.FeatureToRaster_conversion(PlayaPolysLayer, "FID", "Gully_Mask_Raster.img", Cellsize)

	#Convert Poly verticies to points, extract raster value to poly points, convert poly to raster
	arcpy.FeatureVerticesToPoints_management(PlayaPolysLayer, "Gulley_Boundary_Points.shp", "ALL")
	ExtractValuesToPoints("Gulley_Boundary_Points.shp", HUC_DEM, "Gully_Points_with_Elevation.shp", "NONE", "VALUE_ONLY")

	#create tin, tin to raster
	output_tin = OutputLocation + "/Poly_Boundary_Tin"
	arcpy.CreateTin_3d(output_tin, sr, "Gully_Points_with_Elevation.shp RASTERVALU masspoints", "DELAUNAY")
	TinRastCellSize = "CELLSIZE " + Cellsize
	arcpy.TinRaster_3d(output_tin, "cap_raster", "FLOAT", "", TinRastCellSize, "")

	#sets elevation pixels outside of polygon of interest to null. Then ignore pixels with negative depth values 
	outElevationraster = SetNull((IsNull("Gully_Mask_Raster.img")), HUC_DEM)
	outDepthraster = Con("cap_raster" > outElevationraster, "cap_raster" - outElevationraster)
	
	#calculates volume above raster, adds output to the poly shp
	arcpy.SurfaceVolume_3d(outDepthraster, '', 'ABOVE')
	result = arcpy.GetMessages()
	volume = float(re.findall(r'Volume= *([\d\.]+)', result)[0])
	arcpy.CalculateField_management(PlayaPolysLayer, "Volume", volume)
	arcpy.AddMessage("Playa volume: %s" % (str(volume)))
	
	#cleaning up intermediate files
	print "cleaning"
	for volfile in ["Gulley_Boundary_Points.shp", "Gully_Mask_Raster.img", "Gully_Points_with_Elevation.shp", 
						outElevationraster, outDepthraster, "cap_raster", output_tin]:
		if arcpy.Exists(volfile):
			arcpy.Delete_management(volfile)
	arcpy.AddMessage("Done cleaning intermediate files.")
	##########################

	#calculating and reporting process time
	print playaname

	#cleanup intermediate raster files
	for filename in ["playa_rast", "punched_DEM", "buff_perim"]:
		if arcpy.Exists(filename):
			arcpy.Delete_management(filename)

	row = cursor.next()

arcpy.DeleteField_management("Playa_Watersheds.shp", ["GRIDCODE", "ID"])
arcpy.AddMessage("Cleaning up intermediate files...")
for filename in ["single_playa_poly_buff.shp", "single_playa_buff_line.shp", "playa_buff_perim", "playa_rast", 
					"punched_DEM", "filled_DEM", "flowdir", "watershed"]:
	if arcpy.Exists(filename):
		arcpy.Delete_management(filename)
	print "Deleting intermediate files"
arcpy.AddMessage("Done cleaning intermediate files.")

arcpy.AddMessage("======================================")
arcpy.AddMessage("Done!")
arcpy.AddMessage("======================================")




